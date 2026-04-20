"""
降水变率量化计算核心函数（支持 NetCDF 多格点）
基于 Zhang 等 (2024, Science) 方法
所有函数均支持基准期参数 baseline_years=(start, end)
"""
import numpy as np
import xarray as xr
from scipy import stats

def compute_precip_variability_split(ds, split_year=2015):
    """
    分段计算降水变率：
    - 2014年及以前用历史段自己的气候态和趋势
    - 2015年及以后用未来段自己的气候态和趋势
    返回：
        hist_var: xr.DataArray(year, lat, lon)
        hist_years: ndarray
        fut_var: xr.DataArray(year, lat, lon)
        fut_years: ndarray
    """
    import pandas as pd
    pr = get_precip_var(ds).load()
    time_all = pd.to_datetime(pr.time.values)
    years_all = time_all.year.values
    doy_all = time_all.dayofyear.values
    # 历史段
    mask_hist = years_all < split_year
    pr_hist = pr.values[mask_hist]
    years_hist = years_all[mask_hist]
    doy_hist = doy_all[mask_hist]
    pr_anom_hist = remove_annual_cycle(pr_hist, years_hist, doy_hist, baseline_years=None)
    pr_detrend_hist = remove_linear_trend(pr_anom_hist)
    annual_var_hist, year_unique_hist = calc_annual_precip_variability(pr_detrend_hist, years_hist)
    hist_var = xr.DataArray(
        annual_var_hist,
        dims=('year', 'lat', 'lon'),
        coords={'year': year_unique_hist, 'lat': pr.lat, 'lon': pr.lon}
    )
    # 未来段
    mask_fut = years_all >= split_year
    pr_fut = pr.values[mask_fut]
    years_fut = years_all[mask_fut]
    doy_fut = doy_all[mask_fut]
    pr_anom_fut = remove_annual_cycle(pr_fut, years_fut, doy_fut, baseline_years=None)
    pr_detrend_fut = remove_linear_trend(pr_anom_fut)
    annual_var_fut, year_unique_fut = calc_annual_precip_variability(pr_detrend_fut, years_fut)
    fut_var = xr.DataArray(
        annual_var_fut,
        dims=('year', 'lat', 'lon'),
        coords={'year': year_unique_fut, 'lat': pr.lat, 'lon': pr.lon}
    )
    return hist_var, year_unique_hist, fut_var, year_unique_fut

def annual_precip_variability_trend(annual_var, years, baseline_years=None):
    """
    计算年降水变率（标准差）趋势（%/10年，逐格点），可指定趋势计算时间段
    参数：
        annual_var: ndarray, shape=(year, lat, lon)，每年标准差
        years: ndarray, shape=(year,)
        baseline_years: (start, end) 或 None，指定趋势计算的时间段（如(2016,2050)）
    返回：
        trend_pct_decade: ndarray, shape=(lat, lon)
    """
    from scipy import stats
    if baseline_years is not None:
        mask = (years >= baseline_years[0]) & (years <= baseline_years[1])
        years_sel = years[mask]
        annual_var_sel = annual_var[mask]
    else:
        years_sel = years
        annual_var_sel = annual_var
    mean_sigma = np.nanmean(annual_var_sel, axis=0)  # 选定时段气候平均 σ̄
    trend = np.full(mean_sigma.shape, np.nan)
    for i in range(mean_sigma.shape[0]):
        for j in range(mean_sigma.shape[1]):
            yv = annual_var_sel[:, i, j]
            if np.all(np.isnan(yv)) or np.nanmean(yv) == 0:
                continue
            slope, _, _, _, _ = stats.linregress(years_sel, yv)
            # 归一化为百分比，并转换为每10年
            trend[i, j] = (slope / mean_sigma[i, j]) * 100 * 10
    return trend
def calc_annual_precip_variability(data, years):
    """
    计算每年逐格点降水变率（标准差）
    参数：
        data: ndarray, shape=(time, lat, lon)，去除年循环和趋势后的降水异常
        years: ndarray, shape=(time,)
    返回：
        annual_var: ndarray, shape=(year, lat, lon)
        year_unique: ndarray, shape=(year,)
    """
    year_unique = np.unique(years)
    annual_var = np.full((len(year_unique), data.shape[1], data.shape[2]), np.nan)
    for k, y in enumerate(year_unique):
        idx = (years == y)
        annual_var[k] = np.nanstd(data[idx, ...], axis=0)
    return annual_var, year_unique



def compute_precip_variability(ds, baseline_years=(1979,2014)):
    """
    计算降水变率（标准差，逐格点），自动识别降水变量名，基准期可指定。
    参数：
        ds: xarray.Dataset，包含降水变量（pr/pre/precipitation/precip）
        baseline_years: (start, end)，气候平均和变率计算的基准期
    返回：
        xr.DataArray, dims=(lat, lon)
    """
    import pandas as pd
    pr = get_precip_var(ds).load()
    # 全时段
    time_all = pd.to_datetime(pr.time.values)
    years_all = time_all.year.values
    doy_all = time_all.dayofyear.values
    # 用全时段数据计算气候态和趋势
    pr_anom = remove_annual_cycle(pr.values, years_all, doy_all, baseline_years=None)
    pr_detrend = remove_linear_trend(pr_anom)
    # 计算全时段逐年标准差
    annual_var, year_unique = calc_annual_precip_variability(pr_detrend, years_all)
    return xr.DataArray(
        annual_var,
        dims=('year', 'lat', 'lon'),
        coords={'year': year_unique, 'lat': pr.lat, 'lon': pr.lon}
    )
def get_precip_var(ds):
    """
    自动识别主流降水变量名（pr, pre, precipitation, precip），返回DataArray。
    若未找到则抛出异常。
    """
    precip_var_names = ['pr', 'pre', 'precipitation', 'precip']
    for var in ds.data_vars:
        if str(var).lower() in precip_var_names:
            return ds[var]
    raise ValueError(f"未找到降水变量，支持名: {precip_var_names}, 实际: {list(ds.data_vars)}")

def remove_annual_cycle(precip, years, doy, baseline_years=None):
    """
    去除年循环（季节变化），可指定基准期。
    参数：
        precip: ndarray, shape=(time, lat, lon)，多年逐日降水
        years: ndarray, shape=(time,)
        doy: ndarray, shape=(time,)
        baseline_years: (start, end) 或 None，若指定则只用该区间数据计算气候平均
    返回：
        precip_anom: ndarray, shape=(time, lat, lon)，去除年循环后的异常值
    """
    if baseline_years is not None:
        mask = (years >= baseline_years[0]) & (years <= baseline_years[1])
        doy_base = doy[mask]
        precip_base = precip[mask]
    else:
        doy_base = doy
        precip_base = precip
    doy_unique = np.unique(doy_base)
    clim = np.full((len(doy_unique),) + precip.shape[1:], np.nan)
    for i, d in enumerate(doy_unique):
        clim[i] = np.nanmean(precip_base[doy_base == d], axis=0)
    doy_idx = np.searchsorted(doy_unique, doy)
    precip_clim = clim[doy_idx, ...]
    precip_anom = precip - precip_clim
    return precip_anom

def remove_linear_trend(data):
    """
    去除长期线性趋势（逐格点）
    参数：
        data: ndarray, shape=(time, lat, lon)
    返回：
        data_detrend: ndarray, shape=(time, lat, lon)
    """
    t = np.arange(data.shape[0])
    data_detrend = np.full_like(data, np.nan)
    for i in range(data.shape[1]):
        for j in range(data.shape[2]):
            y = data[:, i, j]
            if np.all(np.isnan(y)):
                continue
            isnan = np.isnan(y)
            t_valid = t[~isnan]
            y_valid = y[~isnan]
            if len(y_valid) < 2:
                continue
            slope, intercept, _, _, _ = stats.linregress(t_valid, y_valid)
            trend = slope * t + intercept
            data_detrend[:, i, j] = y - trend
    return data_detrend

def calc_precip_variability(data):
    """
    计算降水变率（标准差，逐格点）
    参数：
        data: ndarray, shape=(time, lat, lon)
    返回：
        variability: ndarray, shape=(lat, lon)
    """
    return np.nanstd(data, axis=0)

def calc_variability_trend(data, years, doy):
    """
    计算变率的线性趋势（%/10年，逐格点）
    参数：
        data: ndarray, shape=(time, lat, lon)
        years: ndarray, shape=(time,)
        doy: ndarray, shape=(time,)
    返回：
        trend_pct_decade: ndarray, shape=(lat, lon)
    """
    year_unique = np.unique(years)
    var_series = np.full((len(year_unique), data.shape[1], data.shape[2]), np.nan)
    for k, y in enumerate(year_unique):
        idx = (years == y)
        var_series[k] = np.nanstd(data[idx, ...], axis=0)
    trend = np.full(data.shape[1:], np.nan)
    mean_var = np.nanmean(var_series, axis=0)
    for i in range(data.shape[1]):
        for j in range(data.shape[2]):
            yv = var_series[:, i, j]
            if np.all(np.isnan(yv)) or np.nanmean(yv) == 0:
                continue
            slope, _, _, _, _ = stats.linregress(year_unique, yv)
            trend[i, j] = (slope / mean_var[i, j]) * 100 * 10
    return trend

