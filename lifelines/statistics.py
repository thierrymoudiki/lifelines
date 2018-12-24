# -*- coding: utf-8 -*-
from __future__ import print_function
from itertools import combinations

import numpy as np
from scipy import stats
import pandas as pd

from lifelines.utils import (
    group_survival_table_from_events,
    significance_code,
    significance_codes_as_text,
    _to_list,
    string_justify,
    _to_array,
    format_p_value,
)


def sample_size_necessary_under_cph(power, ratio_of_participants, p_exp, p_con, postulated_hazard_ratio, alpha=0.05):
    """
    This computes the sample size for needed power to compare two groups under a Cox
    Proportional Hazard model.

    Parameters
    ----------

    power : float
        power to detect the magnitude of the hazard ratio as small as that specified by postulated_hazard_ratio.
    ratio_of_participants: ratio of participants in experimental group over control group.
    
    p_exp : float
        probability of failure in experimental group over period of study.
    
    p_con : float 
        probability of failure in control group over period of study
    
    postulated_hazard_ratio : float 
        the postulated hazard ratio
    
    alpha : float, optional (default=0.05)
        type I error rate


    Returns
    -------

    n_exp : integer
        the samples sizes need for the experiment to achieve desired power

    n_con : integer
        the samples sizes need for the control group to achieve desired power


    Examples
    --------
    >>> from lifelines.statistics import sample_size_necessary_under_cph
    >>> 
    >>> desired_power = 0.8
    >>> ratio_of_participants = 1.
    >>> p_exp = 0.25
    >>> p_con = 0.35
    >>> postulated_hazard_ratio = 0.7
    >>> n_exp, n_con = sample_size_necessary_under_cph(desired_power, ratio_of_participants, p_exp, p_con, postulated_hazard_ratio)
    >>> # (421, 421)

    Notes
    -----
    `Reference <https://cran.r-project.org/web/packages/powerSurvEpi/powerSurvEpi.pdf>`_.

    See Also
    --------
    power_under_cph
    """

    def z(p):
        return stats.norm.ppf(p)

    m = (
        1.0
        / ratio_of_participants
        * ((ratio_of_participants * postulated_hazard_ratio + 1.0) / (postulated_hazard_ratio - 1.0)) ** 2
        * (z(1.0 - alpha / 2.0) + z(power)) ** 2
    )

    n_exp = m * ratio_of_participants / (ratio_of_participants * p_exp + p_con)
    n_con = m / (ratio_of_participants * p_exp + p_con)

    return int(np.ceil(n_exp)), int(np.ceil(n_con))


def power_under_cph(n_exp, n_con, p_exp, p_con, postulated_hazard_ratio, alpha=0.05):
    """
    This computes the power of the hypothesis test that the two groups, experiment and control,
    have different hazards (that is, the relative hazard ratio is different from 1.)

    Parameters
    ----------

    n_exp : integer
        size of the experiment group.
    
    n_con : integer
        size of the control group.
    
    p_exp : float
        probability of failure in experimental group over period of study.
    
    p_con : float
        probability of failure in control group over period of study
    
    postulated_hazard_ratio : float 
    the postulated hazard ratio
    
    alpha : float, optional (default=0.05)
        type I error rate

    Returns
    -------

    power : float
        power to detect the magnitude of the hazard ratio as small as that specified by postulated_hazard_ratio.


    Notes
    -----
    `Reference <https://cran.r-project.org/web/packages/powerSurvEpi/powerSurvEpi.pdf>`_.


    See Also
    --------
    sample_size_necessary_under_cph
    """

    def z(p):
        return stats.norm.ppf(p)

    m = n_exp * p_exp + n_con * p_con
    k = float(n_exp) / float(n_con)
    return stats.norm.cdf(
        np.sqrt(k * m) * abs(postulated_hazard_ratio - 1) / (k * postulated_hazard_ratio + 1) - z(1 - alpha / 2.0)
    )


def logrank_test(durations_A, durations_B, censorship_A=None, censorship_B=None, alpha=0.95, t_0=-1, **kwargs):
    """
    Measures and reports on whether two intensity processes are different. That is, given two
    event series, determines whether the data generating processes are statistically different.
    The test-statistic is chi-squared under the null hypothesis.

     - H_0: both event series are from the same generating processes
     - H_A: the event series are from different generating processes.


    This implicitly uses the log-rank weights.

    Parameters
    ----------

    durations_A: iterable
        a (n,) list-like of event durations (birth to death,...) for the first population.

    durations_B: iterable
        a (n,) list-like of event durations (birth to death,...) for the second population.

    censorship_A: iterable, optional
        a (n,) list-like of censorship flags, (1 if observed, 0 if not), for the first population. 
        Default assumes all observed.

    censorship_B: iterable, optional
        a (n,) list-like of censorship flags, (1 if observed, 0 if not), for the second population. 
        Default assumes all observed.

    t_0: float, optional (default=-1)
        the final time period under observation, -1 for all time.

    alpha: float, optional (default=0.95)
        the confidence level

    kwargs: 
        add keywords and meta-data to the experiment summary


    Returns
    -------

    results : StatisticalResult
      a StatisticalResult object with properties 'p_value', 'summary', 'test_statistic', 'print_summary'

    Examples
    --------
    >>> T1 = [1, 4, 10, 12, 12, 3, 5.4]
    >>> E1 = [1, 0, 1,  0,  1,  1, 1]
    >>>
    >>> T2 = [4, 5, 7, 11, 14, 20, 8, 8]
    >>> E2 = [1, 1, 1, 1,  1,  1,  1, 1]
    >>>
    >>> from lifelines.statistics import logrank_test
    >>> results = logrank_test(T1, T2, censorship_A=E1, censorship_B=E2)
    >>>
    >>> results.print_summary()
    >>> print(results.p_value)        # 0.7676
    >>> print(results.test_statistic) # 0.0872

    Notes
    -----
    This is a special case of the function ``multivariate_logrank_test``, which is used internally. 
    See Survival and Event Analysis, page 108.

    See Also
    --------
    multivariate_logrank_test
    pairwise_logrank_test
    """
    durations_array_A, durations_array_B = (np.array(durations_A), np.array(durations_B))
    if censorship_A is None:
        censorship_A = np.ones(durations_array_A.shape[0])
    if censorship_B is None:
        censorship_B = np.ones(durations_array_B.shape[0])

    durations = np.r_[durations_array_A, durations_array_B]
    groups = np.r_[np.zeros(durations_array_A.shape[0], dtype=int), np.ones(durations_array_B.shape[0], dtype=int)]
    censorship = np.r_[censorship_A, censorship_B]
    return multivariate_logrank_test(durations, groups, censorship, alpha=alpha, t_0=t_0, **kwargs)


def pairwise_logrank_test(
    durations, groups, censorship=None, alpha=0.95, t_0=-1, bonferroni=True, **kwargs
):  # pylint: disable=too-many-locals

    """
    Perform the logrank test pairwise for all n>2 unique groups (use the more appropriate logrank_test for n=2).
    We have to be careful here: if there are n groups, then there are n*(n-1)/2 pairs -- so many pairs increase
    the chance that here will exist a significantly different pair purely by chance. For this reason, we use the
    Bonferroni correction (rewight the alpha value higher to accomidate the multiple tests).


    Parameters
    ----------

    durations: iterable
        a (n,) list-like representing the (possibly partial) durations of all individuals

    groups: iterable
        a (n,) list-like of unique group labels for each individual.

    censorship: iterable, optional
        a (n,) list-like of censorship events: 1 if observed death, 0 if censored. Defaults to all observed.

    t_0: float, optional (default=-1)
        the period under observation, -1 for all time.

    alpha: float, optional (default=0.95)
        the confidence level

    bonferroni: boolean, optional (default=True)
        If True, uses the Bonferroni correction to compare the M=n(n-1)/2 pairs, i.e alpha = alpha/M.

    kwargs: 
        add keywords and meta-data to the experiment summary.


    Returns
    -------

    results : StatisticalResult
        a StatisticalResult object that contains all the pairwise comparisons (try ``StatisticalResult.summary`` or ``StatisticalResult.print_summarty``)


    See Also
    --------
    multivariate_logrank_test
    logrank_test
    """

    if censorship is None:
        censorship = np.ones((durations.shape[0], 1))

    n = np.max(np.asarray(durations).shape)

    groups, durations, censorship = map(
        lambda x: np.asarray(x).reshape(n), [groups, durations, censorship]
    )

    if not (n == durations.shape[0] == censorship.shape[0]):
        raise ValueError("inputs must be of the same length.")

    groups, durations, censorship = pd.Series(groups), pd.Series(durations), pd.Series(censorship)

    unique_groups = np.unique(groups)

    n_unique_groups = unique_groups.shape[0]

    if bonferroni:
        m = 0.5 * n_unique_groups * (n_unique_groups - 1)
        alpha = 1 - (1 - alpha) / m

    result = StatisticalResult([], [], [])

    for i1, i2 in combinations(np.arange(n_unique_groups), 2):
        g1, g2 = unique_groups[[i1, i2]]
        ix1, ix2 = (groups == g1), (groups == g2)
        result += logrank_test(
            durations.loc[ix1],
            durations.loc[ix2],
            censorship.loc[ix1],
            censorship.loc[ix2],
            alpha=alpha,
            t_0=t_0,
            use_bonferroni=bonferroni,
            name=[(g1, g2)],
            **kwargs
        )

    return result


def multivariate_logrank_test(
    durations, groups, censorship=None, alpha=0.95, t_0=-1, **kwargs
):  # pylint: disable=too-many-locals

    """
    This test is a generalization of the logrank_test: it can deal with n>2 populations (and should
    be equal when n=2):

     - H_0: all event series are from the same generating processes
     - H_A: there exist atleast one group that differs from the other.


    Parameters
    ----------

    durations: iterable
        a (n,) list-like representing the (possibly partial) durations of all individuals

    groups: iterable
        a (n,) list-like of unique group labels for each individual.

    censorship: iterable, optional
        a (n,) list-like of censorship events: 1 if observed death, 0 if censored. Defaults to all observed.

    t_0: float, optional (default=-1)
        the period under observation, -1 for all time.

    alpha: float, optional (default=0.95)
        the confidence level

    kwargs: 
        add keywords and meta-data to the experiment summary.


    Returns
    -------

    results : StatisticalResult
       a StatisticalResult object with properties 'p_value', 'summary', 'test_statistic', 'print_summary'

    Examples
    --------

    >>> df = pd.DataFrame({
    >>>    'durations': [5, 3, 9, 8, 7, 4, 4, 3, 2, 5, 6, 7],
    >>>    'events': [1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
    >>>    'groups': [0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2]
    >>> })
    >>> result = multivariate_logrank_test(df['durations'], df['groups'], df['events'])
    >>> result.test_statistic
    >>> result.p_value
    >>> result.print_summary()


    >>> # numpy example
    >>> G = [0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2]
    >>> T = [5, 3, 9, 8, 7, 4, 4, 3, 2, 5, 6, 7]
    >>> E = [1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0]
    >>> result = multivariate_logrank_test(T, G, E)
    >>> result.test_statistic


    See Also
    --------
    pairwise_logrank_test
    logrank_test
    """
    if not (0 < alpha <= 1.0):
        raise ValueError("alpha parameter must be between 0 and 1.")

    durations, groups = np.asarray(durations), np.asarray(groups)
    if censorship is None:
        censorship = np.ones((durations.shape[0], 1))
    else:
        censorship = np.asarray(censorship)

    n = np.max(durations.shape)
    assert n == np.max(durations.shape) == np.max(censorship.shape), "inputs must be of the same length."
    groups, durations, censorship = map(
        lambda x: pd.Series(np.asarray(x).reshape(n)), [groups, durations, censorship]
    )

    unique_groups, rm, obs, _ = group_survival_table_from_events(groups, durations, censorship, limit=t_0)
    n_groups = unique_groups.shape[0]

    # compute the factors needed
    N_j = obs.sum(0).values
    n_ij = rm.sum(0).values - rm.cumsum(0).shift(1).fillna(0)
    d_i = obs.sum(1)
    n_i = rm.values.sum() - rm.sum(1).cumsum().shift(1).fillna(0)
    ev = n_ij.mul(d_i / n_i, axis="index").sum(0)

    # vector of observed minus expected
    Z_j = N_j - ev

    assert abs(Z_j.sum()) < 10e-8, "Sum is not zero."  # this should move to a test eventually.

    # compute covariance matrix
    factor = (((n_i - d_i) / (n_i - 1)).replace([np.inf, np.nan], 1)) * d_i / n_i ** 2
    n_ij["_"] = n_i.values
    V_ = n_ij.mul(np.sqrt(factor), axis="index").fillna(0)
    V = -np.dot(V_.T, V_)
    ix = np.arange(n_groups)
    V[ix, ix] = V[ix, ix] - V[-1, ix]
    V = V[:-1, :-1]

    # take the first n-1 groups
    U = Z_j.iloc[:-1].dot(np.linalg.pinv(V[:-1, :-1])).dot(Z_j.iloc[:-1])  # Z.T*inv(V)*Z

    # compute the p-values and tests
    _, p_value = chisq_test(U, n_groups - 1, alpha)

    return StatisticalResult(
        p_value, U, t_0=t_0, alpha=alpha, null_distribution="chi squared", df=n_groups - 1, **kwargs
    )


class StatisticalResult(object):
    """
    This class holds the result of statistical tests, like logrank and proportional hazard tests, with a nice
    printer wrapper to display the results. 

    Note
    -----
    This class' API changed in version 0.16.0. 
    
    Parameters
    ----------
    p_value: iterable or float
        the p-values of a statistical test(s)
    test_statistic: iterable or float
        the test statistics of a statistical test(s). Must be the same size as p-values if iterable. 
    name: iterable or string
        if this class holds multiple results (ex: from a pairwise comparison), this can hold the names. Must be the same size as p-values if iterable. 
    kwargs: 
        additional information to display in ``print_summary()``.

    """

    def __init__(self, p_value, test_statistic, name=None, **kwargs):
        self.p_value = p_value
        self.test_statistic = test_statistic

        self._p_value = _to_array(p_value)
        self._test_statistic = _to_array(test_statistic)

        assert len(self._p_value) == len(self._test_statistic)

        if name is not None:
            self.name = _to_list(name)
            assert len(self.name) == len(self._test_statistic)

        else:
            self.name = None

        for kw, value in kwargs.items():
            setattr(self, kw, value)

        self._kwargs = kwargs

    def print_summary(self):
        """
        Prints a prettier version of the ``summary`` DataFrame with more metadata.

        """
        print(self.__unicode__())

    @property
    def summary(self):
        """
        
        Returns
        -------

        summary: DataFrame
            a DataFrame containing the test statistics and the p-value

        """
        cols = ["test_statistic", "p"]

        # test to see if self.names is a tuple
        if self.name and isinstance(self.name[0], tuple):
            index = pd.MultiIndex.from_tuples(self.name)
        else:
            index = self.name

        return pd.DataFrame(list(zip(self._test_statistic, self._p_value)), columns=cols, index=index).sort_index()

    def __repr__(self):
        return "<lifelines.StatisticalResult: \n%s\n>" % self.__unicode__()

    def __unicode__(self):
        # pylint: disable=unnecessary-lambda

        meta_data = self._pretty_print_meta_data(self._kwargs)
        df = self.summary
        df["log(p)"] = np.log(df["p"])
        df[""] = [significance_code(p) for p in self._p_value]

        s = ""
        s += "\n" + meta_data + "\n"
        s += "---\n"
        s += df.to_string(
            float_format=lambda f: "{:4.2f}".format(f), index=self.name is not None, formatters={"p": format_p_value}
        )

        s += "\n---"
        s += "\n" + significance_codes_as_text()
        return s

    def _pretty_print_meta_data(self, dictionary):
        longest_key = max([len(k) for k in dictionary])
        justify = string_justify(longest_key)
        s = ""
        for k, v in dictionary.items():
            s += "{} = {}\n".format(justify(k), v)

        return s

    def __add__(self, other):
        """useful for aggregating results easily"""
        p_values = np.r_[self._p_value, other._p_value]
        test_statistics = np.r_[self._test_statistic, other._test_statistic]
        names = self.name + other.name
        kwargs = dict(list(self._kwargs.items()) + list(other._kwargs.items()))
        return StatisticalResult(p_values, test_statistics, name=names, **kwargs)


def chisq_test(U, degrees_freedom, alpha):
    p_value = stats.chi2.sf(U, degrees_freedom)
    if p_value < 1 - alpha:
        return True, p_value
    return None, p_value


def two_sided_z_test(Z, alpha):
    p_value = 1 - np.max(stats.norm.cdf(Z), 1 - stats.norm.cdf(Z))
    if p_value < 1 - alpha / 2.0:
        return True, p_value
    return None, p_value


def proportional_hazard_test(fitted_cox_model, training_df, alpha=0.95, time_transform=lambda x: x, **kwargs):
    # r uses the defalt `km`, we use `identity`
    events = fitted_cox_model.event_observed
    deaths = events.sum()

    scaled_resids = fitted_cox_model.compute_residuals(training_df, kind="scaled_schoenfeld")

    times = time_transform(fitted_cox_model.durations.loc[events])
    times -= times.mean()

    T = (times.values[:, None] * scaled_resids.values).sum(0) ** 2 / (
        deaths * np.diag(fitted_cox_model.variance_matrix_) * (times ** 2).sum()
    )
    p_values = _to_array([chisq_test(t, 1, alpha)[1] for t in T])
    return StatisticalResult(
        p_values,
        T,
        name=fitted_cox_model.hazards_.columns.tolist(),
        alpha=alpha,
        test_name="proportional_hazard_test",
        time_transform=time_transform,
        null_distribution="chi squared",
        df=1,
        **kwargs
    )
