# -*-coding:utf-8 -*-
'''
@Author:  Haoran Yu
@Contact: yuhaoran251@mails.ucas.ac.cn
@Date: 2026/1/19 16:51
@Version: 3.5 - BCSD批量处理
@Copyright: Copyright (c) 2026 Haoran Yu
@Desc: BCSD批量处理：指定模式处理
@Order: 批量完整流程
'''

import xarray as xr
import numpy as np
import pandas as pd
import os
import time
import re
import glob
import cftime
from typing import cast
from scipy.interpolate import UnivariateSpline, RegularGridInterpolator
from scipy.fftpack import fft, ifft
import warnings

warnings.filterwarnings('ignore')




# ==================== 处理参数设置 ====================
# TARGET_LON_RES 和 TARGET_LAT_RES 以观测数据分辨率为准，在SD函数内部自动获取
WINDOW_SIZE = 15
N_QUANTILES = 50
MIN_PRECIP = np.float32(1e-4)
MAX_RATIO = np.float32(10.0)
MIN_RATIO = np.float32(0.1)

# 诊断开关：True 时输出每一步统计信息，便于定位全0问题
DEBUG_CHECK = True
DEBUG_PRINT_SAMPLES = 3


# ==================== 辅助函数 ====================
def calculate_bounds(coord_values):
    """计算坐标边界"""
    bounds = np.zeros((len(coord_values), 2))
    for i in range(len(coord_values)):
        if i == 0:
            spacing = coord_values[1] - coord_values[0]
            bounds[i] = [coord_values[0] - spacing / 2, coord_values[0] + spacing / 2]
        elif i == len(coord_values) - 1:
            spacing = coord_values[-1] - coord_values[-2]
            bounds[i] = [coord_values[-1] - spacing / 2, coord_values[-1] + spacing / 2]
        else:
            bounds[i] = [(coord_values[i - 1] + coord_values[i]) / 2,
                         (coord_values[i] + coord_values[i + 1]) / 2]
        if bounds[i, 0] > bounds[i, 1]:
            bounds[i] = [bounds[i, 1], bounds[i, 0]]
    return bounds


def get_precip_var_name(ds, candidates=('pr', 'pre', 'precip', 'precipitation')):
    """
    获取降水变量名。

    参数:
        ds (xr.Dataset): 输入数据集。
        candidates (tuple[str, ...]): 优先匹配的变量名候选。

    返回:
        str: 识别到的降水变量名。
    """
    for name in candidates:
        if name in ds.data_vars:
            return name
    for name in ds.data_vars:
        lower = name.lower()
        if 'pr' in lower or 'precip' in lower:
            return name
    raise KeyError(f"未找到降水变量，现有变量: {list(ds.data_vars)}")


def convert_precip_to_mm_day(da, var_name='precip'):
    """
    将降水数据统一到 mm/day。

    参数:
        da (xr.DataArray): 输入降水数据。
        var_name (str): 变量名，仅用于日志输出。

    返回:
        xr.DataArray: 单位统一后的降水数据。
    """
    units = str(da.attrs.get('units', '')).strip()
    units_norm = units.lower().replace(' ', '')
    if units_norm in ['kgm-2s-1', 'kg/m2/s', 'kgm**-2s**-1', 'kgm-2sec-1']:
        da = da * np.float32(86400.0)
        da.attrs['units'] = 'mm/day'
        print(f"     单位转换: {var_name} {units} -> mm/day")
    return da


def cftime_to_datetime(cftime_obj):
    """将cftime对象转换为datetime字符串"""
    return pd.Timestamp(year=cftime_obj.year, month=cftime_obj.month, day=cftime_obj.day)


def parse_cftime_date(cftime_obj):
    """解析cftime对象的年月日"""
    if hasattr(cftime_obj, 'year'):
        return cftime_obj.year, cftime_obj.month, cftime_obj.day
    return None, None, None


def detect_calendar_type(time_values):
    """检测日历类型"""
    try:
        # 检查第一个时间值是否是cftime对象
        first_time = time_values[0]

        # 如果是cftime对象，根据类型判断
        if hasattr(first_time, 'calendar'):
            calendar = first_time.calendar.lower()
            if '360' in calendar:
                return "360_day", 360
            elif 'noleap' in calendar or '365' in calendar:
                return "noleap", 365
            else:
                return "gregorian", 366

        # 否则尝试统计1961年的天数
        year_1961_mask = []
        for t in time_values[:1000]:
            try:
                if hasattr(t, 'year'):
                    year_1961_mask.append(t.year == 1961)
                else:
                    dt = pd.to_datetime(str(t))
                    year_1961_mask.append(dt.year == 1961)
            except:
                year_1961_mask.append(False)

        year_1961_count = sum(year_1961_mask)

        if year_1961_count == 365:
            return "noleap", 365
        elif year_1961_count == 360:
            return "360_day", 360
        else:
            return "gregorian", 366
    except:
        return "gregorian", 366

        print(f"\n[BCSD主函数]\n  历史期: {gcm_hist_path}\n  观测: {obs_path}\n  未来期: {gcm_fut_path}\n  输出目录: {output_dir}\n  模式: {model_name}\n  参考期: {ref_start_year}-{ref_end_year}")
def calculate_doy(dates, calendar_type):
    """计算日序数"""
    doy_list = []
    for date in dates:
        if calendar_type == "360_day":
            if hasattr(date, 'day'):
                doy = (date.month - 1) * 30 + date.day
            else:
                # 尝试解析为datetime
                try:
                    if hasattr(date, 'year'):
                        doy = (date.month - 1) * 30 + date.day
                    else:
                        dt = pd.to_datetime(str(date))
                        doy = (dt.month - 1) * 30 + dt.day
                except:
                    doy = date.timetuple().tm_yday
        elif calendar_type == "noleap":
            month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            if hasattr(date, 'day'):
                doy = sum(month_days[:date.month - 1]) + date.day
            else:
                try:
                    dt = pd.to_datetime(str(date))
                    doy = sum(month_days[:dt.month - 1]) + dt.day
                except:
                    doy = date.timetuple().tm_yday
        else:
            if hasattr(date, 'dayofyear'):
                doy = date.dayofyear
            else:
                try:
                    dt = pd.to_datetime(str(date))
                    doy = dt.dayofyear
                except:
                    doy = date.timetuple().tm_yday
        doy_list.append(doy)
    return np.array(doy_list, dtype=np.int32)


def create_cdf_spline(gcm_data, obs_data, n_quantiles=50):
    """创建CDF分位数匹配的三次光滑样条传递函数"""
    gcm_clean = gcm_data[~np.isnan(gcm_data)]
    obs_clean = obs_data[~np.isnan(obs_data)]

    gcm_clean = np.maximum(gcm_clean, 0.0)
    obs_clean = np.maximum(obs_clean, 0.0)

    if len(gcm_clean) < 20 or len(obs_clean) < 20:
        return None

    n_min = min(len(gcm_clean), len(obs_clean))
    n_q = min(n_quantiles, max(20, int(n_min / 25)))

    quantiles = np.linspace(0.02, 0.98, n_q)

    try:
        gcm_q = np.percentile(gcm_clean, quantiles * 100)
        obs_q = np.percentile(obs_clean, quantiles * 100)

        for i in range(1, len(gcm_q)):
            if gcm_q[i] <= gcm_q[i - 1]:
                gcm_q[i] = gcm_q[i - 1] + 1e-10

        spline = UnivariateSpline(gcm_q, obs_q, s=0.8 * len(gcm_q), k=3)

        gcm_min, gcm_max = gcm_q[0], gcm_q[-1]
        obs_min, obs_max = obs_q[0], obs_q[-1]

        def transfer_func(x):
            is_scalar = np.isscalar(x)
            if is_scalar:
                x = np.array([x])

            x_array = np.asarray(x, dtype=np.float64)
            result = np.zeros_like(x_array)

            in_range_mask = (x_array >= gcm_min) & (x_array <= gcm_max)
            if np.any(in_range_mask):
                result[in_range_mask] = spline(x_array[in_range_mask])

            below_mask = x_array < gcm_min
            above_mask = x_array > gcm_max

            if np.any(below_mask):
                result[below_mask] = obs_min
            if np.any(above_mask):
                result[above_mask] = obs_max

            result = np.maximum(result, 0.0)
            result = np.where(result < 1e-10, 0.0, result)

            if is_scalar:
                return float(result[0])
            return result

        return transfer_func
    except Exception as e:
        print(f"创建传递函数失败: {e}")
        return None


def fft_smooth_three_harmonics(daily_series, n_days, n_harmonics=3):
    """FFT平滑气候态（保留前三个谐波）"""
    if len(daily_series) != n_days:
        raise ValueError(f"序列长度应为{n_days}")

    series = daily_series.copy().astype(np.float32)
    nan_mask = np.isnan(series)

    if np.all(nan_mask):
        return series

    if np.any(nan_mask):
        indices = np.arange(len(series), dtype=np.float32)
        valid = ~nan_mask
        if np.sum(valid) > 1:
            series = np.interp(indices, indices[valid], series[valid]).astype(np.float32)
        else:
            series[nan_mask] = np.nanmean(series).astype(np.float32)

    fft_result = fft(series)
    n = len(fft_result)

    keep_indices = [0]
    for i in range(1, n_harmonics + 1):
        keep_indices.append(i)
        keep_indices.append(n - i)

    mask = np.zeros(n, dtype=bool)
    mask[keep_indices] = True

    filtered_fft = fft_result.copy()
    filtered_fft[~mask] = 0

    smoothed = np.real(ifft(filtered_fft)).astype(np.float32)
    smoothed = smoothed[:len(daily_series)]

    if np.any(nan_mask):
        smoothed[nan_mask] = daily_series[nan_mask]

    smoothed = np.where(smoothed < 0, 0, smoothed)
    return smoothed


def _safe_min(arr):
    """计算最小值（自动忽略非有限值）。"""
    finite = arr[np.isfinite(arr)]
    return float(np.min(finite)) if finite.size > 0 else np.nan


def _safe_max(arr):
    """计算最大值（自动忽略非有限值）。"""
    finite = arr[np.isfinite(arr)]
    return float(np.max(finite)) if finite.size > 0 else np.nan


def _safe_mean(arr):
    """计算均值（自动忽略非有限值）。"""
    finite = arr[np.isfinite(arr)]
    return float(np.mean(finite)) if finite.size > 0 else np.nan


def print_array_diagnostics(name, data):
    """
    打印数组诊断信息。

    参数:
        name (str): 当前检查步骤名。
        data (np.ndarray | xr.DataArray): 待检查数据。
    """
    arr = np.asarray(data)
    total = arr.size
    finite_mask = np.isfinite(arr)
    finite_count = int(np.sum(finite_mask))
    nan_count = int(np.sum(np.isnan(arr)))
    inf_count = int(total - finite_count - nan_count)

    if finite_count > 0:
        finite = arr[finite_mask]
        zero_count = int(np.sum(np.isclose(finite, 0.0, atol=1e-12)))
        non_zero_count = finite_count - zero_count
        min_v = _safe_min(finite)
        max_v = _safe_max(finite)
        mean_v = _safe_mean(finite)
        p95_v = float(np.percentile(finite, 95))
    else:
        zero_count = 0
        non_zero_count = 0
        min_v = np.nan
        max_v = np.nan
        mean_v = np.nan
        p95_v = np.nan

    finite_ratio = (finite_count / total * 100.0) if total > 0 else np.nan
    zero_ratio = (zero_count / finite_count * 100.0) if finite_count > 0 else np.nan
    non_zero_ratio = (non_zero_count / finite_count * 100.0) if finite_count > 0 else np.nan

    print(f"     [检查] {name}")
    print(f"       shape={arr.shape}, dtype={arr.dtype}, 总数={total}")
    print(f"       有效值={finite_count} ({finite_ratio:.2f}%), NaN={nan_count}, Inf={inf_count}")
    print(f"       非零值={non_zero_count} ({non_zero_ratio:.2f}%), 零值={zero_count} ({zero_ratio:.2f}%)")
    print(f"       min={min_v:.6g}, max={max_v:.6g}, mean={mean_v:.6g}, p95={p95_v:.6g}")

    if finite_count > 0 and zero_count == finite_count:
        print(f"       [警告] {name} 的有效值全部为0，请重点检查上一步。")


# ==================== BC函数：偏差校正 ====================
def BC(obs_path, gcm_hist_path, gcm_fut_path, model_name, ref_start_year, ref_end_year):
    """
    偏差校正函数（内部使用，不保存中间结果）

    参数:
        obs_path (str): 观测数据NetCDF文件路径。
        gcm_hist_path (str): GCM历史期文件路径。
        gcm_fut_path (str): GCM未来期文件路径。
        model_name (str): 模式名称（用于日志输出）。

    返回:
        dict | None: 成功时返回校正结果字典，失败返回None。
    """
    print(f"\n  偏差校正 (BC): {model_name}")

    start_time = time.time()

    try:
        # 1. 读取数据
        print("  1. 读取数据...")

        # 读取观测数据
        obs_ds = xr.open_dataset(obs_path)
        obs_time_coord = 'Time' if 'Time' in obs_ds.coords else 'time'
        obs_ref = obs_ds.sel({obs_time_coord: slice(f'{ref_start_year}', f'{ref_end_year}')})
        obs_var_name = get_precip_var_name(obs_ref)
        obs_pr = convert_precip_to_mm_day(obs_ref[obs_var_name], var_name=f'obs_{obs_var_name}')
        print(f"     观测数据: {obs_pr.shape}")
        if DEBUG_CHECK:
            print_array_diagnostics("BC-观测原始", obs_pr.values)

        # 读取GCM数据，不自动解码时间
        gcm_hist_ds = xr.open_dataset(gcm_hist_path, decode_times=False)
        gcm_hist_pr = convert_precip_to_mm_day(gcm_hist_ds['pr'], var_name='gcm_hist_pr')
        print(f"     GCM历史数据: {gcm_hist_pr.shape}")
        if DEBUG_CHECK:
            print_array_diagnostics("BC-GCM历史原始", gcm_hist_pr.values)

        gcm_fut_ds = xr.open_dataset(gcm_fut_path, decode_times=False)
        gcm_fut_pr = convert_precip_to_mm_day(gcm_fut_ds['pr'], var_name='gcm_fut_pr')
        print(f"     GCM未来数据: {gcm_fut_pr.shape}")
        if DEBUG_CHECK:
            print_array_diagnostics("BC-GCM未来原始", gcm_fut_pr.values)

        # 2. 观测数据升尺度
        print("  2. 观测数据升尺度...")

        # 获取坐标
        obs_lat = obs_pr.Lat.values if 'Lat' in obs_pr.coords else obs_pr.lat.values
        obs_lon = obs_pr.Lon.values if 'Lon' in obs_pr.coords else obs_pr.lon.values
        gcm_lat = gcm_hist_pr.Lat.values if 'Lat' in gcm_hist_pr.coords else gcm_hist_pr.lat.values
        gcm_lon = gcm_hist_pr.Lon.values if 'Lon' in gcm_hist_pr.coords else gcm_hist_pr.lon.values

        # 计算边界
        obs_lat_bounds = calculate_bounds(obs_lat)
        obs_lon_bounds = calculate_bounds(obs_lon)
        gcm_lat_bounds = calculate_bounds(gcm_lat)
        gcm_lon_bounds = calculate_bounds(gcm_lon)

        # 初始化升尺度数组
        n_time_obs = len(obs_pr.Time) if 'Time' in obs_pr.coords else len(obs_pr.time)
        n_lat_gcm = len(gcm_lat)
        n_lon_gcm = len(gcm_lon)
        obs_coarse_values = np.full((n_time_obs, n_lat_gcm, n_lon_gcm), np.nan)

        # 面积加权平均
        obs_area_weights = np.cos(np.radians(obs_lat))[:, np.newaxis]

        for i in range(n_lat_gcm):
            if i % 5 == 0 or i == n_lat_gcm - 1:
                print(f"     纬度进度: {i + 1}/{n_lat_gcm}")

            for j in range(n_lon_gcm):
                lat_mask = (obs_lat >= gcm_lat_bounds[i, 0]) & (obs_lat <= gcm_lat_bounds[i, 1])
                lon_mask = (obs_lon >= gcm_lon_bounds[j, 0]) & (obs_lon <= gcm_lon_bounds[j, 1])

                lat_indices = np.where(lat_mask)[0]
                lon_indices = np.where(lon_mask)[0]

                if len(lat_indices) > 0 and len(lon_indices) > 0:
                    for t in range(n_time_obs):
                        obs_subset = obs_pr.values[
                            t, lat_indices[0]:lat_indices[-1] + 1, lon_indices[0]:lon_indices[-1] + 1]
                        weights_subset = obs_area_weights[lat_indices[0]:lat_indices[-1] + 1, :]
                        weights_subset = np.repeat(weights_subset, len(lon_indices), axis=1)

                        valid_mask = ~np.isnan(obs_subset)

                        if np.any(valid_mask):
                            weighted_sum = np.nansum(obs_subset * weights_subset)
                            total_weight = np.nansum(weights_subset * valid_mask)

                            if total_weight > 0:
                                obs_coarse_values[t, i, j] = weighted_sum / total_weight

        print("     观测数据升尺度完成！")
        if DEBUG_CHECK:
            print_array_diagnostics("BC-观测升尺度到GCM网格", obs_coarse_values)

        # 3. 时间对齐处理
        print("  3. 时间对齐处理...")

        gcm_time_coord = 'Time' if 'Time' in gcm_hist_ds.coords else 'time'
        gcm_time_values = gcm_hist_ds[gcm_time_coord].values

        # 获取观测日期
        obs_dates = []
        for t in obs_ref[obs_time_coord].values:
            if hasattr(t, 'year'):
                obs_dates.append(pd.Timestamp(year=t.year, month=t.month, day=t.day))
            else:
                t_str = str(t).split('T')[0] if 'T' in str(t) else str(t)
                obs_dates.append(pd.Timestamp(t_str))

        # 解码GCM时间
        try:
            # 尝试解码时间
            gcm_hist_decoded = xr.decode_cf(gcm_hist_ds)
            gcm_time_decoded = gcm_hist_decoded[gcm_time_coord].values
            # 检测日历类型
            calendar_type, max_doy = detect_calendar_type(gcm_time_decoded)
        except:
            # 如果解码失败，尝试手动处理
            print("     时间解码失败，尝试手动处理...")
            # 检查文件信息中的日历类型
            calendar = gcm_hist_ds[gcm_time_coord].attrs.get('calendar', '')
            if calendar:
                if '360' in str(calendar):
                    calendar_type = "360_day"
                    max_doy = 360
                elif 'noleap' in str(calendar) or '365' in str(calendar):
                    calendar_type = "noleap"
                    max_doy = 365
                else:
                    calendar_type = "gregorian"
                    max_doy = 366
            else:
                # 默认使用360_day，因为UKESM1-0-LL使用360天日历
                calendar_type = "360_day"
                max_doy = 360

        print(f"     日历类型: {calendar_type}, 最大DOY: {max_doy}")

        # 日历调整
        if calendar_type == "noleap":
            feb29_mask = np.array([(d.month == 2 and d.day == 29) for d in obs_dates])
            if feb29_mask.sum() > 0:
                obs_coarse_values = obs_coarse_values[~feb29_mask, :, :]
                obs_dates = [d for i, d in enumerate(obs_dates) if not feb29_mask[i]]
        elif calendar_type == "360_day":
            remove_mask = np.array([d.day == 31 for d in obs_dates])
            if remove_mask.sum() > 0:
                obs_coarse_values = obs_coarse_values[~remove_mask, :, :]
                obs_dates = [d for i, d in enumerate(obs_dates) if not remove_mask[i]]

        # 对齐长度
        min_length = min(len(obs_dates), len(gcm_hist_pr[gcm_time_coord]))
        obs_coarse_values = obs_coarse_values[:min_length, :, :]
        obs_dates = obs_dates[:min_length]
        gcm_hist_values = gcm_hist_pr.values[:min_length, :, :]
        gcm_fut_values = gcm_fut_pr.values

        # 同时裁剪GCM DataArray以保证坐标一致
        gcm_hist_pr_aligned = gcm_hist_pr.isel({gcm_time_coord: slice(0, min_length)})

        print(f"     对齐长度: {min_length} 天")
        if DEBUG_CHECK:
            print_array_diagnostics("BC-时间对齐后观测升尺度", obs_coarse_values)
            print_array_diagnostics("BC-时间对齐后GCM历史", gcm_hist_values)
            print_array_diagnostics("BC-时间对齐后GCM未来", gcm_fut_values)

        # 4. 计算DOY
        print("  4. 计算DOY...")

        obs_doy = calculate_doy(obs_dates, calendar_type)

        # 计算GCM DOY
        gcm_hist_doy = []
        for t_idx in range(min_length):
            # 使用基于日历类型的DOY计算
            doy = ((t_idx % max_doy) + 1)  # 简单按顺序分配DOY
            gcm_hist_doy.append(doy)

        gcm_fut_doy = []
        for t_idx in range(len(gcm_fut_pr[gcm_time_coord])):
            doy = ((t_idx % max_doy) + 1)
            gcm_fut_doy.append(doy)

        gcm_hist_doy = np.array(gcm_hist_doy, dtype=np.int32)
        gcm_fut_doy = np.array(gcm_fut_doy, dtype=np.int32)

        print(f"     历史期: {len(gcm_hist_doy)}天, 未来期: {len(gcm_fut_doy)}天")
        if DEBUG_CHECK:
            print(f"     [检查] BC-DOY覆盖: obs唯一DOY={len(np.unique(obs_doy))}, "
                  f"hist唯一DOY={len(np.unique(gcm_hist_doy))}, fut唯一DOY={len(np.unique(gcm_fut_doy))}")

        # 5. CDF分位数匹配
        print("  5. CDF分位数匹配偏差校正...")

        n_time_hist = len(gcm_hist_doy)
        n_time_fut = len(gcm_fut_doy)
        n_lat_gcm = gcm_hist_values.shape[1]
        n_lon_gcm = gcm_hist_values.shape[2]

        corrected_hist_values = np.zeros_like(gcm_hist_values)
        corrected_fut_values = np.zeros_like(gcm_fut_values)

        print(f"     滑动窗口: ±{WINDOW_SIZE}天, 网格点: {n_lat_gcm}×{n_lon_gcm}")

        total_doy = 0
        missing_window_doy = 0
        built_func_doy = 0

        # 逐网格点校正
        for lat_idx in range(n_lat_gcm):
            if lat_idx % 5 == 0 or lat_idx == n_lat_gcm - 1:
                progress = (lat_idx + 1) / n_lat_gcm * 100
                print(f"     纬度进度: {lat_idx + 1}/{n_lat_gcm} ({progress:.1f}%)")

            for lon_idx in range(n_lon_gcm):
                # 提取数据
                obs_series = obs_coarse_values[:, lat_idx, lon_idx]
                gcm_hist_series = gcm_hist_values[:, lat_idx, lon_idx]
                gcm_fut_series = gcm_fut_values[:, lat_idx, lon_idx]

                # 存储传递函数
                doy_funcs = {}

                # 为每个DOY建立传递函数
                for doy in range(1, max_doy + 1):
                    total_doy += 1
                    # 收集观测窗口数据
                    obs_indices = np.where(obs_doy == doy)[0]
                    obs_window = []
                    for idx in obs_indices:
                        start = max(0, idx - WINDOW_SIZE)
                        end = min(len(obs_series) - 1, idx + WINDOW_SIZE)
                        obs_window.extend(obs_series[start:end + 1])

                    # 收集GCM历史窗口数据
                    gcm_indices = np.where(gcm_hist_doy == doy)[0]
                    gcm_window = []
                    for idx in gcm_indices:
                        start = max(0, idx - WINDOW_SIZE)
                        end = min(n_time_hist - 1, idx + WINDOW_SIZE)
                        gcm_window.extend(gcm_hist_series[start:end + 1])

                    if len(obs_window) == 0 or len(gcm_window) == 0:
                        missing_window_doy += 1
                        doy_funcs[doy] = None
                        continue

                    # 创建传递函数
                    func = create_cdf_spline(np.array(gcm_window), np.array(obs_window), N_QUANTILES)
                    doy_funcs[doy] = func
                    if func is not None:
                        built_func_doy += 1

                # 校正历史期数据
                for t in range(n_time_hist):
                    doy = int(gcm_hist_doy[t])
                    val = gcm_hist_series[t]

                    if not np.isnan(val) and doy in doy_funcs and doy_funcs[doy] is not None:
                        corrected_hist_values[t, lat_idx, lon_idx] = doy_funcs[doy](val)
                    else:
                        corrected_hist_values[t, lat_idx, lon_idx] = val

                # 校正未来期数据
                for t in range(n_time_fut):
                    doy = int(gcm_fut_doy[t])
                    val = gcm_fut_series[t]

                    if not np.isnan(val) and doy in doy_funcs and doy_funcs[doy] is not None:
                        corrected_fut_values[t, lat_idx, lon_idx] = doy_funcs[doy](val)
                    else:
                        corrected_fut_values[t, lat_idx, lon_idx] = val

        print("     偏差校正完成！")
        if DEBUG_CHECK:
            print(f"     [检查] BC-传递函数统计: 总DOY样本={total_doy}, 窗口缺失={missing_window_doy}, "
                  f"成功构建={built_func_doy}")
            print_array_diagnostics("BC-历史校正结果", corrected_hist_values)
            print_array_diagnostics("BC-未来校正结果", corrected_fut_values)

        # 创建校正数据数组
        corrected_hist_pr = xr.DataArray(
            corrected_hist_values,
            dims=gcm_hist_pr_aligned.dims,
            coords=gcm_hist_pr_aligned.coords,
            attrs=gcm_hist_pr_aligned.attrs.copy()
        )

        corrected_fut_pr = xr.DataArray(
            corrected_fut_values,
            dims=gcm_fut_pr.dims,
            coords=gcm_fut_pr.coords,
            attrs=gcm_fut_pr.attrs.copy()
        )

        # 关闭数据集
        obs_ds.close()
        gcm_hist_ds.close()
        gcm_fut_ds.close()

        elapsed_time = time.time() - start_time
        print(f"     偏差校正耗时: {elapsed_time:.1f}秒")

        # 返回BC结果，供SD使用
        return {
            'corrected_hist_pr': corrected_hist_pr,
            'corrected_fut_pr': corrected_fut_pr,
            'calendar_type': calendar_type,
            'max_doy': max_doy,
            'gcm_time_coord': gcm_time_coord,
            'gcm_lat_coord': 'Lat' if 'Lat' in gcm_hist_ds.coords else 'lat',
            'gcm_lon_coord': 'Lon' if 'Lon' in gcm_hist_ds.coords else 'lon',
            'original_hist_path': gcm_hist_path,
            'original_fut_path': gcm_fut_path,
            'model_name': model_name
        }

    except Exception as e:
        print(f"     偏差校正失败: {str(e)}")
        import traceback
        traceback.print_exc()
        for ds_obj in ['obs_ds', 'gcm_hist_ds', 'gcm_fut_ds']:
            if ds_obj in locals():
                try:
                    locals()[ds_obj].close()
                except Exception:
                    pass
        return None


# ==================== SD函数：空间降尺度 ====================
def area_weighted_regrid(source_lat, source_lon, source_data, target_lat, target_lon):
    """使用面积加权平均将高分辨率数据粗化到低分辨率网格"""
    source_lat_bounds = calculate_bounds(source_lat)
    source_lon_bounds = calculate_bounds(source_lon)
    target_lat_bounds = calculate_bounds(target_lat)
    target_lon_bounds = calculate_bounds(target_lon)

    n_lat_target = len(target_lat)
    n_lon_target = len(target_lon)
    regridded_data = np.full((n_lat_target, n_lon_target), np.nan, dtype=np.float32)

    source_area_weights = np.cos(np.radians(source_lat))[:, np.newaxis]

    for i in range(n_lat_target):
        for j in range(n_lon_target):
            # 找到与目标网格重叠的源网格
            lat_mask = (source_lat >= target_lat_bounds[i, 0]) & (source_lat <= target_lat_bounds[i, 1])
            lon_mask = (source_lon >= target_lon_bounds[j, 0]) & (source_lon <= target_lon_bounds[j, 1])

            lat_indices = np.where(lat_mask)[0]
            lon_indices = np.where(lon_mask)[0]

            if len(lat_indices) > 0 and len(lon_indices) > 0:
                source_subset = source_data[lat_indices[0]:lat_indices[-1] + 1, lon_indices[0]:lon_indices[-1] + 1]
                weights_subset = source_area_weights[lat_indices[0]:lat_indices[-1] + 1, :]
                weights_subset = np.repeat(weights_subset, len(lon_indices), axis=1)

                valid_mask = ~np.isnan(source_subset)
                if np.any(valid_mask):
                    weighted_sum = np.nansum(source_subset * weights_subset)
                    total_weight = np.nansum(weights_subset * valid_mask)
                    if total_weight > 0:
                        regridded_data[i, j] = weighted_sum / total_weight
    return regridded_data


def SD(obs_path, bc_result, output_dir, ref_start_year, ref_end_year):
    """
    空间降尺度主函数

    参数:
        obs_path (str): 观测数据NetCDF文件路径。
        bc_result (dict): BC函数返回的校正结果字典。
        output_dir (str): BCSD结果输出目录。

    返回:
        dict | None: 成功时返回输出文件路径信息，失败返回None。
    """
    model_name = bc_result['model_name']
    calendar_type = bc_result['calendar_type']
    max_doy = bc_result['max_doy']
    gcm_time_coord = bc_result['gcm_time_coord']
    original_hist_path = bc_result.get('original_hist_path')  # 原始历史文件路径
    original_fut_path = bc_result.get('original_fut_path')  # 原始未来文件路径

    print(f"\n  空间降尺度 (SD): {model_name}")

    start_time = time.time()

    try:
        print("  1. 读取数据...")

        # 读取观测数据
        obs_ds = xr.open_dataset(obs_path)
        obs_time_coord = 'Time' if 'Time' in obs_ds.coords else 'time'
        obs_ref = obs_ds.sel({obs_time_coord: slice(f'{ref_start_year}', f'{ref_end_year}')})
        obs_var_name = get_precip_var_name(obs_ref)
        obs_pr = convert_precip_to_mm_day(obs_ref[obs_var_name], var_name=f'obs_{obs_var_name}')

        # 获取BC校正后的数据
        corrected_hist_pr = bc_result['corrected_hist_pr']
        corrected_fut_pr = bc_result['corrected_fut_pr']

        print(f"     观测数据: {obs_pr.shape}")
        print(f"     BC历史数据: {corrected_hist_pr.shape}")
        print(f"     BC未来数据: {corrected_fut_pr.shape}")
        if DEBUG_CHECK:
            print_array_diagnostics("SD-观测输入", obs_pr.values)
            print_array_diagnostics("SD-BC历史输入", corrected_hist_pr.values)
            print_array_diagnostics("SD-BC未来输入", corrected_fut_pr.values)

        # 2. 读取原始GCM数据以获取时间变量（不解码时间）
        print("  2. 读取原始时间坐标...")

        # 读取历史期原始时间坐标
        hist_ds_original = xr.open_dataset(original_hist_path, decode_times=False)
        hist_time_var = cast(xr.DataArray, hist_ds_original[gcm_time_coord])

        # 如果BC校正裁剪了数据，需要同步裁剪时间坐标
        n_time_hist = corrected_hist_pr.shape[0]
        if len(hist_time_var) > n_time_hist:
            hist_time_var = hist_time_var.isel({gcm_time_coord: slice(0, n_time_hist)})

        print(f"     历史原始时间: {len(hist_time_var)}个时间点")
        hist_time_values = np.asarray(hist_time_var.data)
        print(f"     历史原始时间类型: {type(hist_time_values[0])}")
        print(f"     历史原始时间属性: {dict(hist_time_var.attrs)}")

        # 读取未来期原始时间坐标
        fut_ds_original = xr.open_dataset(original_fut_path, decode_times=False)
        fut_time_var = cast(xr.DataArray, fut_ds_original[gcm_time_coord])

        # 确保未来时间坐标长度匹配
        n_time_future = corrected_fut_pr.shape[0]
        if len(fut_time_var) > n_time_future:
            fut_time_var = fut_time_var.isel({gcm_time_coord: slice(0, n_time_future)})
        elif len(fut_time_var) < n_time_future:
            if len(fut_time_var) == 0:
                raise ValueError("未来时间坐标为空，无法与未来数据对齐")
            # 如果未来时间坐标长度不足，使用循环扩展
            print(f"     警告: 未来时间坐标长度({len(fut_time_var)})小于数据长度({n_time_future})")
            # 简单重复最后一个时间点（这只是一个临时解决方案）
            fut_time_var = xr.concat([fut_time_var] * (n_time_future // len(fut_time_var) + 1), dim=gcm_time_coord)
            fut_time_var = fut_time_var.isel({gcm_time_coord: slice(0, n_time_future)})

        print(f"     未来原始时间: {len(fut_time_var)}个时间点")
        fut_time_values = np.asarray(fut_time_var.data)
        print(f"     未来原始时间类型: {type(fut_time_values[0])}")

        # 3. 计算FFT平滑气候场
        print("  3. 计算FFT平滑气候场...")

        # 获取观测坐标
        obs_lat_coord = 'Lat' if 'Lat' in obs_ref.coords else 'lat'
        obs_lon_coord = 'Lon' if 'Lon' in obs_ref.coords else 'lon'

        obs_pr_array = obs_pr.values.astype(np.float32)
        n_days = max_doy
        n_lat_obs = obs_pr_array.shape[1]
        n_lon_obs = obs_pr_array.shape[2]

        # 获取观测日期
        obs_dates = []
        for t in obs_ref[obs_time_coord].values:
            if hasattr(t, 'year'):
                obs_dates.append(pd.Timestamp(year=t.year, month=t.month, day=t.day))
            else:
                t_str = str(t).split('T')[0] if 'T' in str(t) else str(t)
                obs_dates.append(pd.Timestamp(t_str))

        # 日历调整
        if calendar_type == "noleap":
            feb29_mask = np.array([(d.month == 2 and d.day == 29) for d in obs_dates])
            if feb29_mask.sum() > 0:
                obs_pr_array = obs_pr_array[~feb29_mask, :, :]
                obs_dates = [d for i, d in enumerate(obs_dates) if not feb29_mask[i]]
        elif calendar_type == "360_day":
            remove_mask = np.array([d.day == 31 for d in obs_dates])
            if remove_mask.sum() > 0:
                obs_pr_array = obs_pr_array[~remove_mask, :, :]
                obs_dates = [d for i, d in enumerate(obs_dates) if not remove_mask[i]]

        # 计算DOY
        obs_doy = calculate_doy(obs_dates, calendar_type)

        # 计算每日气候态
        obs_clim_values = np.zeros((n_days, n_lat_obs, n_lon_obs), dtype=np.float32)
        obs_clim_counts = np.zeros((n_days, n_lat_obs, n_lon_obs), dtype=np.float32)

        for t in range(len(obs_pr_array)):
            doy_idx = int(obs_doy[t]) - 1
            if doy_idx < n_days:
                obs_clim_values[doy_idx] += obs_pr_array[t]
                obs_clim_counts[doy_idx] += (~np.isnan(obs_pr_array[t])).astype(np.float32)

        # 计算平均值
        obs_clim_values = np.where(obs_clim_counts > 0, obs_clim_values / obs_clim_counts, np.nan).astype(np.float32)
        obs_clim_values = np.where(obs_clim_values < 0, 0, obs_clim_values)

        # FFT平滑气候态
        obs_clim_smooth = np.zeros_like(obs_clim_values, dtype=np.float32)

        for lat_idx in range(n_lat_obs):
            for lon_idx in range(n_lon_obs):
                daily_series = obs_clim_values[:, lat_idx, lon_idx]

                if np.any(~np.isnan(daily_series)):
                    try:
                        smoothed = fft_smooth_three_harmonics(daily_series, n_days, n_harmonics=3)
                        obs_clim_smooth[:, lat_idx, lon_idx] = smoothed
                    except:
                        obs_clim_smooth[:, lat_idx, lon_idx] = daily_series
                else:
                    obs_clim_smooth[:, lat_idx, lon_idx] = daily_series

        # 处理NaN值
        obs_clim_median = np.nanmedian(obs_clim_smooth).astype(np.float32)
        obs_clim_smooth = np.where(np.isnan(obs_clim_smooth), obs_clim_median * 0.1, obs_clim_smooth).astype(np.float32)
        obs_clim_smooth = np.where(obs_clim_smooth < 0, 0, obs_clim_smooth).astype(np.float32)
        if DEBUG_CHECK:
            print_array_diagnostics("SD-观测逐日气候态(平滑前)", obs_clim_values)
            print_array_diagnostics("SD-观测逐日气候态(平滑后)", obs_clim_smooth)

        # 4. 空间降尺度
        print("  4. 空间降尺度...")

        # 获取模式数据
        gcm_lat_coord = bc_result['gcm_lat_coord']
        gcm_lon_coord = bc_result['gcm_lon_coord']

        hist_bc_data = corrected_hist_pr.values.astype(np.float32)
        future_bc_data = corrected_fut_pr.values.astype(np.float32)

        # 获取模式网格
        model_lon = corrected_hist_pr[gcm_lon_coord].values.astype(np.float32)
        model_lat = corrected_hist_pr[gcm_lat_coord].values.astype(np.float32)


        # 根据观测数据自动获取分辨率
        obs_lon_vals = obs_ref[obs_lon_coord].values
        obs_lat_vals = obs_ref[obs_lat_coord].values
        if len(obs_lon_vals) > 1:
            lon_res = float(np.round(np.abs(obs_lon_vals[1] - obs_lon_vals[0]), 6))
        else:
            lon_res = 0.25
        if len(obs_lat_vals) > 1:
            lat_res = float(np.round(np.abs(obs_lat_vals[1] - obs_lat_vals[0]), 6))
        else:
            lat_res = 0.25
        target_lon = np.arange(obs_lon_vals.min(), obs_lon_vals.max() + lon_res, lon_res).astype(np.float32)
        target_lat = np.arange(obs_lat_vals.min(), obs_lat_vals.max() + lat_res, lat_res).astype(np.float32)
        if DEBUG_CHECK:
            print(f"     [检查] SD-网格尺寸: 观测网格=({n_lat_obs}, {n_lon_obs}), 目标网格=({len(target_lat)}, {len(target_lon)})")
            if (len(target_lat) != n_lat_obs) or (len(target_lon) != n_lon_obs):
                print("       [警告] 目标网格尺寸与观测气候态不一致，可能导致结果异常或回退。")

        # 初始化降尺度结果
        hist_downscaled = np.zeros((n_time_hist, len(target_lat), len(target_lon)), dtype=np.float32)
        future_downscaled = np.zeros((n_time_future, len(target_lat), len(target_lon)), dtype=np.float32)

        # 预构建目标网格点（RegularGridInterpolator输入）
        target_lat_grid, target_lon_grid = np.meshgrid(target_lat, target_lon, indexing='ij')
        target_points = np.column_stack((target_lat_grid.ravel(), target_lon_grid.ravel())).astype(np.float32)

        # 历史数据降尺度
        print("     处理历史数据...")
        hist_sample_steps = sorted(set([0, max(0, n_time_hist // 2), max(0, n_time_hist - 1)]))
        for t in range(n_time_hist):
            model_slice = hist_bc_data[t]
            doy_idx = t % n_days  # 简单基于时间索引的DOY

            # 获取当天观测气候态
            obs_clim_today = obs_clim_smooth[doy_idx].copy()

            # 将观测气候态粗化到模式网格
            obs_clim_coarse = area_weighted_regrid(
                source_lat=obs_ref[obs_lat_coord].values,
                source_lon=obs_ref[obs_lon_coord].values,
                source_data=obs_clim_today,
                target_lat=model_lat,
                target_lon=model_lon
            ).astype(np.float32)
            obs_clim_coarse = np.where(obs_clim_coarse < 0, 0, obs_clim_coarse)

            # 处理数据
            model_slice_safe = np.where(model_slice < MIN_PRECIP, MIN_PRECIP, model_slice).astype(np.float32)
            obs_clim_coarse_safe = np.where(obs_clim_coarse < MIN_PRECIP, MIN_PRECIP, obs_clim_coarse).astype(
                np.float32)

            # 计算相对变化
            relative_change = model_slice_safe / obs_clim_coarse_safe
            relative_change = np.clip(relative_change, MIN_RATIO, MAX_RATIO).astype(np.float32)
            relative_change = np.where(relative_change < 0, 0, relative_change)

            # 获取高分辨率气候态
            obs_clim_highres = obs_clim_smooth[doy_idx].astype(np.float32)
            obs_clim_highres_safe = np.where(np.isnan(obs_clim_highres), MIN_PRECIP, obs_clim_highres).astype(np.float32)
            obs_clim_highres_safe = np.where(obs_clim_highres_safe < 0, 0, obs_clim_highres_safe)

            try:
                # 双线性插值相对变化
                interp_func = RegularGridInterpolator(
                    (model_lat, model_lon),
                    relative_change,
                    method='linear',
                    bounds_error=False,
                    fill_value=cast(float, None)
                )
                relative_change_highres = interp_func(target_points).reshape(len(target_lat), len(target_lon)).astype(
                    np.float32)

                # 计算降尺度结果
                downscaled_result = (relative_change_highres * obs_clim_highres_safe).astype(np.float32)
                hist_downscaled[t] = np.clip(downscaled_result, 0, None)

                if DEBUG_CHECK and t in hist_sample_steps:
                    print(f"     [检查] SD-历史样本时间步 t={t}")
                    print_array_diagnostics("SD-历史 model_slice", model_slice)
                    print_array_diagnostics("SD-历史 obs_clim_coarse", obs_clim_coarse)
                    print_array_diagnostics("SD-历史 relative_change", relative_change)
                    print_array_diagnostics("SD-历史 downscaled_result", downscaled_result)
            except Exception as e:
                print(f"     历史数据降尺度失败，时间步 {t}: {e}")
                hist_downscaled[t] = obs_clim_highres_safe

        # 未来数据降尺度
        print("     处理未来数据...")
        future_sample_steps = sorted(set([0, max(0, n_time_future // 2), max(0, n_time_future - 1)]))
        for t in range(n_time_future):
            model_slice = future_bc_data[t]
            doy_idx = t % n_days  # 简单基于时间索引的DOY

            # 获取当天观测气候态
            obs_clim_today = obs_clim_smooth[doy_idx].copy()

            # 将观测气候态粗化到模式网格
            obs_clim_coarse = area_weighted_regrid(
                source_lat=obs_ref[obs_lat_coord].values,
                source_lon=obs_ref[obs_lon_coord].values,
                source_data=obs_clim_today,
                target_lat=model_lat,
                target_lon=model_lon
            ).astype(np.float32)

            # 处理数据
            model_slice_safe = np.where(model_slice < MIN_PRECIP, MIN_PRECIP, model_slice).astype(np.float32)
            obs_clim_coarse_safe = np.where(obs_clim_coarse < MIN_PRECIP, MIN_PRECIP, obs_clim_coarse).astype(
                np.float32)

            # 计算相对变化
            relative_change = model_slice_safe / obs_clim_coarse_safe
            relative_change = np.clip(relative_change, MIN_RATIO, MAX_RATIO).astype(np.float32)

            # 获取高分辨率气候态
            obs_clim_highres = obs_clim_smooth[doy_idx].astype(np.float32)
            obs_clim_highres_safe = np.where(np.isnan(obs_clim_highres), MIN_PRECIP, obs_clim_highres).astype(
                np.float32)

            try:
                # 双线性插值相对变化
                interp_func = RegularGridInterpolator(
                    (model_lat, model_lon),
                    relative_change,
                    method='linear',
                    bounds_error=False,
                    fill_value=cast(float, None)
                )
                relative_change_highres = interp_func(target_points).reshape(len(target_lat), len(target_lon)).astype(
                    np.float32)

                # 计算降尺度结果
                downscaled_result = (relative_change_highres * obs_clim_highres_safe).astype(np.float32)
                downscaled_result = np.where(downscaled_result < 0, 0, downscaled_result)
                future_downscaled[t] = downscaled_result

                if DEBUG_CHECK and t in future_sample_steps:
                    print(f"     [检查] SD-未来样本时间步 t={t}")
                    print_array_diagnostics("SD-未来 model_slice", model_slice)
                    print_array_diagnostics("SD-未来 obs_clim_coarse", obs_clim_coarse)
                    print_array_diagnostics("SD-未来 relative_change", relative_change)
                    print_array_diagnostics("SD-未来 downscaled_result", downscaled_result)
            except Exception as e:
                print(f"     未来数据降尺度失败，时间步 {t}: {e}")
                future_downscaled[t] = obs_clim_highres_safe


        # 写入前再次全量非负截断，确保无负降水
        hist_downscaled = np.where(hist_downscaled < 0, 0, hist_downscaled)
        future_downscaled = np.where(future_downscaled < 0, 0, future_downscaled)
        # 5. 保存BCSD结果（使用原始时间变量）
        print("  5. 保存BCSD结果...")

        # 以模型名创建输出目录
        model_output_dir = os.path.join(output_dir, str(model_name))
        os.makedirs(model_output_dir, exist_ok=True)

        # 保存文件名
        hist_bcsd_output_path = os.path.join(model_output_dir, f"{model_name}_historical_BCSD.nc")
        fut_bcsd_output_path = os.path.join(model_output_dir, f"{model_name}_future_BCSD.nc")

        # 准备时间坐标 - 直接使用原始GCM的时间变量
        time_coords_hist = np.asarray(hist_time_var.data)
        time_coords_fut = np.asarray(fut_time_var.data)

        print(f"     历史时间坐标类型: {type(time_coords_hist[0])}")
        print(f"     未来时间坐标类型: {type(time_coords_fut[0])}")

        # 创建数据集 - 直接使用原始时间坐标，保持不解码状态
        ds_hist_bcsd = xr.Dataset(
            {
                'pr': xr.DataArray(
                    hist_downscaled.astype(np.float32),
                    dims=[gcm_time_coord, obs_lat_coord, obs_lon_coord],
                    coords={
                        gcm_time_coord: time_coords_hist,
                        obs_lat_coord: target_lat.astype(np.float32),
                        obs_lon_coord: target_lon.astype(np.float32)
                    },
                    attrs={
                        'long_name': 'BCSD Downscaled precipitation (historical)',
                        'units': 'mm/day',
                        'method': 'BCSD: CDF Quantile-Matched + FFT smoothed climatology + bilinear interpolation',
                        'calendar_type': calendar_type,
                        # 'resolution'和'reference_period'可由调用者自定义
                        'version': 'v4.0',
                        'model_name': model_name,
                        'processing_step': 'BCSD_complete',
                        'time_coordinate': 'original GCM time coordinate (not decoded)'
                    }
                )
            }
        )

        # 保留原始时间变量的属性
        if hasattr(hist_time_var, 'attrs'):
            ds_hist_bcsd[gcm_time_coord].attrs.update(hist_time_var.attrs)
            ds_hist_bcsd[gcm_time_coord].attrs['note'] = 'Original GCM time coordinate, not decoded'

        ds_future_bcsd = xr.Dataset(
            {
                'pr': xr.DataArray(
                    future_downscaled.astype(np.float32),
                    dims=[gcm_time_coord, obs_lat_coord, obs_lon_coord],
                    coords={
                        gcm_time_coord: time_coords_fut,
                        obs_lat_coord: target_lat.astype(np.float32),
                        obs_lon_coord: target_lon.astype(np.float32)
                    },
                    attrs={
                        'long_name': 'BCSD Downscaled precipitation (future)',
                        'units': 'mm/day',
                        'method': 'BCSD: CDF Quantile-Matched + FFT smoothed climatology + bilinear interpolation',
                        'calendar_type': calendar_type,
                        # 'resolution'和'reference_period'可由调用者自定义
                        'version': 'v4.0',
                        'model_name': model_name,
                        'processing_step': 'BCSD_complete',
                        'time_coordinate': 'original GCM time coordinate (not decoded)'
                    }
                )
            }
        )

        # 保留未来时间变量的属性
        if hasattr(fut_time_var, 'attrs'):
            ds_future_bcsd[gcm_time_coord].attrs.update(fut_time_var.attrs)
            ds_future_bcsd[gcm_time_coord].attrs['note'] = 'Original GCM time coordinate, not decoded'

        # 保存BCSD结果文件
        print("     编码并保存NetCDF文件...")

        # 编码历史数据 - 明确指定不解码时间
        encoding = {
            'pr': {'dtype': 'float32', 'zlib': True, 'complevel': 4},
            gcm_time_coord: {'dtype': 'double', '_FillValue': None}
        }

        try:
            ds_hist_bcsd.to_netcdf(
                hist_bcsd_output_path,
                encoding=encoding,
                unlimited_dims=[gcm_time_coord]
            )
        except Exception as e:
            print(f"     历史数据保存失败: {e}")
            # 尝试更简单的保存方式
            ds_hist_bcsd.to_netcdf(hist_bcsd_output_path, unlimited_dims=[gcm_time_coord])

        # 编码未来数据
        try:
            ds_future_bcsd.to_netcdf(
                fut_bcsd_output_path,
                encoding=encoding,
                unlimited_dims=[gcm_time_coord]
            )
        except Exception as e:
            print(f"     未来数据保存失败: {e}")
            ds_future_bcsd.to_netcdf(fut_bcsd_output_path, unlimited_dims=[gcm_time_coord])

        print(f"     BCSD历史数据保存: {hist_bcsd_output_path}")
        print(f"     BCSD未来数据保存: {fut_bcsd_output_path}")

        # 打印时间信息验证
        print(f"\n     时间坐标验证:")
        print(f"       历史: {len(time_coords_hist)}个时间点, 类型: {type(time_coords_hist[0])}")
        print(f"       未来: {len(time_coords_fut)}个时间点, 类型: {type(time_coords_fut[0])}")

        # 检查保存的文件
        try:
            check_hist = xr.open_dataset(hist_bcsd_output_path, decode_times=False)
            check_fut = xr.open_dataset(fut_bcsd_output_path, decode_times=False)
            print(f"       文件验证通过")
            check_hist.close()
            check_fut.close()
        except Exception as e:
            print(f"       文件验证失败: {e}")

        # 关闭数据集
        obs_ds.close()
        hist_ds_original.close()
        fut_ds_original.close()

        elapsed_time = time.time() - start_time
        print(f"     空间降尺度耗时: {elapsed_time:.1f}秒")

        return {
            'hist_bcsd_path': hist_bcsd_output_path,
            'fut_bcsd_path': fut_bcsd_output_path,
            'time_coordinate': gcm_time_coord
        }

    except Exception as e:
        print(f"     空间降尺度失败: {str(e)}")
        import traceback
        traceback.print_exc()
        for ds_obj in ['obs_ds', 'hist_ds_original', 'fut_ds_original']:
            if ds_obj in locals():
                try:
                    locals()[ds_obj].close()
                except Exception:
                    pass
        return None


# ==================== BCSD完整流程函数 ====================
def BCSD(obs_path, gcm_hist_path, gcm_fut_path, model_name, output_dir, ref_start_year, ref_end_year):
    """
    BCSD完整流程：先BC后SD
    """
    print(f"\n处理模式: {model_name}")
    print("=" * 60)

    # 第一步：偏差校正 (BC)
    bc_result = BC(
        obs_path=obs_path,
        gcm_hist_path=gcm_hist_path,
        gcm_fut_path=gcm_fut_path,
        model_name=model_name,
        ref_start_year=ref_start_year,
        ref_end_year=ref_end_year
    )

    if not bc_result:
        print(f"✗ {model_name} BC失败，停止处理")
        return None

    # 第二步：空间降尺度 (SD)
    sd_result = SD(
        obs_path=obs_path,
        bc_result=bc_result,
        output_dir=output_dir,
        ref_start_year=ref_start_year,
        ref_end_year=ref_end_year
    )

    if not sd_result:
        print(f"✗ {model_name} SD失败")
        return None

    print(f"✓ {model_name} BCSD完整流程完成！")
    print("=" * 60)

    return {
        'model_name': model_name,
        'hist_bcsd_path': sd_result['hist_bcsd_path'],
        'fut_bcsd_path': sd_result['fut_bcsd_path']
    }


# ==================== 主程序 ====================
