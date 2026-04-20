# -*-coding:utf-8 -*-
'''
@Author:  Haoran Yu
@Contact: yuhaoran251@mails.ucas.ac.cn
@Date: 2025/12/5 18:25
@Version: 2.1
@Copyright: Copyright (c) 2025 Haoran Yu
@Author: Haoran Yu
@Desc: 极端气候指标计算函数库
'''
import numpy as np
import xarray as xr
from tqdm import tqdm
import warnings
from datetime import datetime, timedelta

"""======================================================辅助函数======================================================"""
"""======================================================辅助函数======================================================"""
"""======================================================辅助函数======================================================"""
"""======================================================辅助函数======================================================"""
"""======================================================辅助函数======================================================"""
"""======================================"""
"""
    稳健的时间转换函数：将任意格式的time维度转换为datetime64[D]（日分辨率）
    支持各种cftime日历类型、数值格式、字符串格式和datetime64格式
    自动修正无效日期（如2月30日）
    """
def _convert_time_to_datetime(pr):
    """
    将输入降水数据的 time 维统一转换为 datetime64[D]。

    参数:
        pr (xarray.DataArray): 包含 time 维的降水数据。

    返回:
        xarray.DataArray: time 已标准化为日分辨率的降水数据。
    """

    time_vals = pr.time.values

    # ==================== 1. 处理cftime类型 ====================
    try:
        import cftime
        if len(time_vals) > 0 and isinstance(time_vals[0], cftime.datetime):
            parsed_times = []
            for t in time_vals:
                year, month, day = t.year, t.month, t.day

                # 修正无效日期
                if month == 2:
                    calendar = getattr(t, 'calendar', 'standard')
                    if calendar in ['noleap', '365_day', '365']:
                        day = min(day, 28)  # 无闰年日历
                    elif calendar in ['360_day', '360']:
                        day = min(day, 30)  # 360天日历
                    else:
                        # 标准日历：检查闰年
                        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                        day = min(day, 29 if is_leap else 28)
                elif month in [4, 6, 9, 11]:
                    day = min(day, 30)  # 小月
                else:
                    day = min(day, 31)  # 大月

                try:
                    dt = datetime(year, month, day)
                    parsed_times.append(np.datetime64(dt))
                except ValueError:
                    # 兜底修正
                    if month == 2:
                        day = 28
                    elif month in [4, 6, 9, 11]:
                        day = 30
                    else:
                        day = 31
                    dt = datetime(year, month, day)
                    parsed_times.append(np.datetime64(dt))

            return pr.assign_coords(time=np.array(parsed_times, dtype='datetime64[D]'))
    except ImportError:
        pass
    except Exception:
        pass  # 继续尝试其他格式

    # ==================== 2. 处理datetime64类型 ====================
    if len(time_vals) > 0 and np.issubdtype(time_vals.dtype, np.datetime64):
        return pr.assign_coords(time=pr.time.dt.floor('D'))

    # ==================== 3. 处理数值型时间 ====================
    if len(time_vals) > 0 and np.issubdtype(time_vals.dtype, np.number):
        parsed_times = []
        for val in time_vals:
            val = float(val)

            # YYYYMMDD格式
            if 19000101 <= val <= 21001231:
                val_int = int(val)
                year = val_int // 10000
                month = (val_int // 100) % 100
                day = val_int % 100

                # 修正日期
                if month == 2:
                    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                    day = min(day, 29 if is_leap else 28)
                elif month in [4, 6, 9, 11]:
                    day = min(day, 30)
                else:
                    day = min(day, 31)

                dt = datetime(year, month, day)
                parsed_times.append(np.datetime64(dt))

            # 年+日序格式
            elif 1900 <= val < 2100:
                year = int(val)
                doy = int(round((val - year) * 1000))
                doy = max(1, min(doy, 366))
                dt = datetime(year, 1, 1) + timedelta(days=doy - 1)
                parsed_times.append(np.datetime64(dt))

            # 时间戳
            elif val > 1e9:
                if val > 1e12:
                    val = val / 1000
                dt = datetime.fromtimestamp(val)
                parsed_times.append(np.datetime64(dt))

        if parsed_times:
            return pr.assign_coords(time=np.array(parsed_times, dtype='datetime64[D]'))

    # ==================== 4. 处理字符串型时间 ====================
    if len(time_vals) > 0 and not np.issubdtype(time_vals.dtype, np.number):
        parsed_times = []
        date_formats = [
            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M', '%Y-%m-%d',
            '%Y/%m/%d', '%Y%m%d', '%Y.%m.%d'
        ]

        for date_str in [str(t).strip() for t in time_vals]:
            parsed = None

            # 尝试各种格式
            for fmt in date_formats:
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    break
                except ValueError as e:
                    # 尝试修正无效日期
                    if "day is out of range for month" in str(e):
                        try:
                            date_part = date_str.split(' ')[0] if ' ' in date_str else date_str
                            parts = date_part.replace('/', '-').replace('.', '-').split('-')

                            if len(parts) == 3:
                                if len(parts[0]) == 4:  # YYYY-MM-DD
                                    year, month, day = map(int, parts)
                                else:  # 尝试其他顺序
                                    try:
                                        datetime.strptime(date_part, '%d-%m-%Y')
                                        day, month, year = map(int, parts)
                                    except:
                                        continue

                                # 修正日期
                                if month == 2:
                                    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                                    day = min(day, 29 if is_leap else 28)
                                elif month in [4, 6, 9, 11]:
                                    day = min(day, 30)
                                else:
                                    day = min(day, 31)

                                corrected_date = f"{year:04d}-{month:02d}-{day:02d}"
                                if ' ' in date_str:
                                    corrected_date = f"{corrected_date} {date_str.split(' ')[1]}"

                                parsed = datetime.strptime(corrected_date, fmt)
                                break
                        except:
                            continue

            if parsed is None:
                # 尝试pandas解析
                try:
                    import pandas as pd
                    parsed = pd.to_datetime(date_str).to_pydatetime()
                except:
                    raise ValueError(f"无法解析时间字符串: {date_str}")

            parsed_times.append(np.datetime64(parsed))

        return pr.assign_coords(time=np.array(parsed_times, dtype='datetime64[D]'))

    # ==================== 5. 未知格式 ====================
    raise ValueError(f"无法识别的时间格式，数据类型: {time_vals.dtype}")
"""======================================"""

# 检查数据格式与逐日特征
def check_data(pr):
    """
    通用降水数据校验函数（含自动时间类型转换）
    :param pr: xarray.DataArray - 待校验的降水数据
    :return: xarray.DataArray - 校验并转换后的降水数据（time为datetime64[D]格式）
    :raises ValueError: 数据校验失败时抛出异常
    """
    # 1. 基础类型校验
    if not isinstance(pr, xr.DataArray):
        raise ValueError(f"输入数据必须是xarray.DataArray类型，当前类型: {type(pr)}")

    # 2. 降水变量名校验（支持气象常用命名）
    valid_var_names = ['pr', 'pre', 'precipitation', 'rain', 'prec', 'tp']
    var_name = str(pr.name).lower() if pr.name is not None else ''
    if var_name not in valid_var_names:
        raise ValueError(
            f"无效的降水变量名: '{pr.name}'，支持的变量名: {', '.join(valid_var_names)}"
        )

    # 3. time维度存在性校验
    if 'time' not in pr.dims:
        raise ValueError("输入数据必须包含'time'维度")

    # 4. 核心：自动转换time维度为datetime64[D]格式
    pr = _convert_time_to_datetime(pr)

    # 5. 逐日数据校验（基于datetime64计算时间间隔）
    time_vals = pr.time.values
    if len(time_vals) < 2:
        raise ValueError("time维度数据量不足，至少需要2个时间点验证逐日特征")

    time_diff = np.diff(time_vals)
    day_diff = np.timedelta64(1, 'D')

    # 计算逐日比例
    daily_ratio = np.sum(time_diff == day_diff) / len(time_diff)

    # 放宽标准：允许最多5%的非逐日间隔（处理气候模型数据的不规则性）
    if daily_ratio < 0.95:
        # 手动计算时间间隔分布（兼容旧版numpy）
        unique_intervals = []
        counts = []

        for interval in time_diff:
            found = False
            for i, u_interval in enumerate(unique_intervals):
                if interval == u_interval:
                    counts[i] += 1
                    found = True
                    break
            if not found:
                unique_intervals.append(interval)
                counts.append(1)

        # 找出主要的时间间隔
        if counts:  # 确保有数据
            max_count = max(counts)
            max_index = counts.index(max_count)
            main_interval = unique_intervals[max_index]
            main_ratio = max_count / len(time_diff)

            if main_ratio >= 0.95:
                # 如果主要间隔是1天，但有一些缺失，允许继续
                if main_interval == day_diff:
                    print(f"注意: 数据有{100 * (1 - daily_ratio):.1f}%的时间间隔不是1天，但主要间隔是1天，继续处理")
                    # 不抛出异常，继续处理
                else:
                    # 主要间隔不是1天，检查是否是气候模型常用间隔
                    main_interval_days = main_interval / np.timedelta64(1, 'D')
                    if abs(main_interval_days - 1.0) < 0.01:
                        # 接近1天（如0.997天或1.003天），可能是日历差异
                        print(f"注意: 主要时间间隔为{main_interval_days:.3f}天，继续处理")
                        # 不抛出异常，继续处理
                    else:
                        # 创建间隔分布字典用于错误信息
                        interval_dist = {}
                        for interval, count in zip(unique_intervals, counts):
                            interval_days = interval / np.timedelta64(1, 'D')
                            interval_dist[f"{interval_days:.3f}天"] = count

                        raise ValueError(
                            f"输入数据非标准逐日数据！仅{daily_ratio * 100:.1f}%的时间间隔为1天\n"
                            f"主要时间间隔: {main_interval} ({main_interval_days:.3f}天)，占比{main_ratio * 100:.1f}%\n"
                            f"时间间隔分布: {interval_dist}\n"
                            f"时间间隔统计：最小={np.min(time_diff)}, 最大={np.max(time_diff)}, 均值={np.mean(time_diff)}"
                        )
            else:
                # 创建间隔分布字典用于错误信息
                interval_dist = {}
                for interval, count in zip(unique_intervals, counts):
                    interval_days = interval / np.timedelta64(1, 'D')
                    interval_dist[f"{interval_days:.3f}天"] = count

                raise ValueError(
                    f"输入数据非标准逐日数据！仅{daily_ratio * 100:.1f}%的时间间隔为1天\n"
                    f"时间间隔分布: {interval_dist}\n"
                    f"时间间隔统计：最小={np.min(time_diff)}, 最大={np.max(time_diff)}, 均值={np.mean(time_diff)}"
                )
        else:
            raise ValueError(
                f"输入数据非标准逐日数据！仅{daily_ratio * 100:.1f}%的时间间隔为1天\n"
                f"时间间隔统计：最小={np.min(time_diff)}, 最大={np.max(time_diff)}, 均值={np.mean(time_diff)}"
            )

    # 6. 年份范围有效性校验
    years = pr.time.dt.year.values
    min_year, max_year = np.min(years), np.max(years)
    if min_year > max_year:
        raise ValueError(f"无效的年份范围: 最小年份={min_year}, 最大年份={max_year}")

    return pr

"""======================================"""

# 计算连续天数辅助函数
def _max_consecutive_true(arr):
    """
    辅助函数：计算布尔序列中最长连续 True 的长度（用于 CDD/CWD）。

    参数:
        arr (numpy.ndarray): 布尔数组，时间维应位于第 0 维。

    返回:
        numpy.float32 或 numpy.ndarray: 最长连续 True 长度。
    """
    if arr.dtype != bool:
        arr = arr.astype(bool)

    if arr.ndim == 1:
        max_len, cur_len = 0, 0
        for val in arr:
            cur_len = cur_len + 1 if val else 0
            max_len = max(max_len, cur_len)
        return np.float32(max_len)

    # 高维数组处理（time轴为首维）
    stacked = np.moveaxis(arr, 0, -1)
    out_shape = stacked.shape[:-1]
    result = np.zeros(out_shape, dtype=np.float32)

    it = np.nditer(result, flags=['multi_index'], op_flags=[['writeonly']])
    while not it.finished:
        idx = it.multi_index
        series = stacked[idx]
        max_len, cur_len = 0, 0
        for val in series:
            cur_len = cur_len + 1 if val else 0
            max_len = max(max_len, cur_len)
        it[0] = max_len
        it.iternext()

    return result


# ====================== 基础降水指数 ======================
# ====================== 基础降水指数 ======================
# ====================== 基础降水指数 ======================
# ====================== 基础降水指数 ======================
# ====================== 基础降水指数 ======================
# ====================== 基础降水指数 ======================
def PRCPTOT(pr):
    """
    逐年年总降水量（PRCPTOT）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    pr = check_data(pr)
    # print("计算年总降水量 (PRCPTOT)")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc="PRCPTOT"):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        annual_sum = year_data.sum(dim='time').astype(np.float32)
        result_list.append(annual_sum)
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)


def R1mm_days(pr):
    """
    逐年 >= 1 mm 降水日数（R1mm_days）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    pr = check_data(pr)
    # print("计算年≥1mm降水日数 (R1mm_days)")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc="R1mm_days"):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        wet_days = (year_data >= 1.0).sum(dim='time').astype(np.float32)
        result_list.append(wet_days)
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)

def SDII(pr):
    """
    逐年简单降水强度（SDII = 年总降水量 / 年湿日数）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    pr = check_data(pr)
    # print("计算年简单降水强度 (SDII)")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc="SDII"):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        annual_sum = year_data.sum(dim='time')
        wet_days = (year_data >= 1.0).sum(dim='time')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            sdii = (annual_sum / wet_days).where(wet_days > 0)
        result_list.append(sdii.astype(np.float32))
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)

def RX1DAY(pr):
    """
    逐年最大日降水量（RX1DAY）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    pr = check_data(pr)
    # print("计算年最大日降水量 (RX1DAY)")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc="RX1DAY"):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        max_precip = year_data.max(dim='time').astype(np.float32)
        result_list.append(max_precip)
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)

def RX5DAY(pr):
    """
    逐年最大 5 日降水量（RX5DAY）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    pr = check_data(pr)
    # print("计算年最大5日降水量 (RX5DAY)")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc="RX5DAY"):
        # 选择该年的数据
        year_data = pr.sel(time=pr.time.dt.year == year)

        # 检查是否有足够的数据（至少30天）
        if len(year_data) < 30:
            print(f"年份{year}数据点不足({len(year_data)})，跳过")
            continue

        try:
            # 计算滑动5日总和
            # 使用rolling方法计算5日滑动总和
            rolling_sum = year_data.rolling(time=5, center=False).sum()

            # 找出最大5日降水量
            max_5day = rolling_sum.max(dim='time').astype(np.float32)

            result_list.append(max_5day)
            year_labels.append(int(year))

        except Exception as e:
            print(f"年份{year}计算RX5DAY时出错: {e}")
            # 创建一个NaN数组作为占位符
            nan_array = xr.full_like(year_data.isel(time=0), np.nan).astype(np.float32)
            result_list.append(nan_array)
            year_labels.append(int(year))

    if not result_list:
        print("错误：没有足够的数据计算RX5DAY")
        return None

    # 合并所有年份的结果
    result = xr.concat(result_list, dim='year').assign_coords(year=year_labels)
    result.name = 'RX5DAY'

    # 添加属性说明
    result.attrs.update({
        'long_name': 'Maximum 5-day precipitation amount',
        'units': pr.attrs.get('units', 'mm'),
        'description': 'Maximum precipitation accumulated over any 5-day period',
        'calculation_method': 'Maximum of 5-day rolling sum',
        'time_period': 'annual',
        'reference': 'ETCCDI_Results Indicator RX5day'
    })
    return result

def CDD(pr):
    """
    逐年最大连续干日数（CDD，<1 mm 为干日）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    pr = check_data(pr)
    # print("计算年最大连续干日数 (CDD)")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc="CDD"):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        dry_mask = (year_data < 1.0)
        max_cdd = xr.apply_ufunc(
            _max_consecutive_true,
            dry_mask,
            input_core_dims=[['time']],
            output_core_dims=[[]],
            vectorize=True,
            output_dtypes=[np.float32]
        )
        result_list.append(max_cdd)
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)

def CWD(pr):
    """
    逐年最大连续湿日数（CWD，>= 1 mm 为湿日）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    pr = check_data(pr)
    # print("计算年最大连续湿日数 (CWD)")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc="CWD"):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        wet_mask = (year_data >= 1.0)
        max_cwd = xr.apply_ufunc(
            _max_consecutive_true,
            wet_mask,
            input_core_dims=[['time']],
            output_core_dims=[[]],
            vectorize=True,
            output_dtypes=[np.float32]
        )
        result_list.append(max_cwd)
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)


# ====================== 固定阈值降水指数 ======================
# ====================== 固定阈值降水指数 ======================
# ====================== 固定阈值降水指数 ======================
# ====================== 固定阈值降水指数 ======================
# ====================== 固定阈值降水指数 ======================
# ====================== 固定阈值降水指数 ======================
# 固定阈值通用计算函数
def _calc_threshold_precip(pr, threshold, metric_name, func_name):
    """
    固定阈值指标通用函数：统计年降水总量。

    参数:
        pr (xarray.DataArray): 日降水数据。
        threshold (float): 日降水阈值（单位与 pr 一致）。
        metric_name (str): 指标中文名称，用于日志输出。
        func_name (str): 指标函数名，用于进度条显示。
    """
    pr = check_data(pr)
    # print(f"计算≥{threshold}mm降水{metric_name} ({func_name})")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        threshold_data = year_data.where(year_data >= threshold, 0)
        total = threshold_data.sum(dim='time').astype(np.float32)
        result_list.append(total)
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)


def _calc_threshold_days(pr, threshold, metric_name, func_name):
    """
    固定阈值指标通用函数：统计年超阈值日数。

    参数:
        pr (xarray.DataArray): 日降水数据。
        threshold (float): 日降水阈值（单位与 pr 一致）。
        metric_name (str): 指标中文名称，用于日志输出。
        func_name (str): 指标函数名，用于进度条显示。
    """
    pr = check_data(pr)
    # print(f"计算≥{threshold}mm降水{metric_name} ({func_name})")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        days = (year_data >= threshold).sum(dim='time').astype(np.float32)
        result_list.append(days)
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)


def _calc_threshold_intensity(pr, threshold, metric_name, func_name):
    """
    固定阈值指标通用函数：统计年超阈值平均强度。

    参数:
        pr (xarray.DataArray): 日降水数据。
        threshold (float): 日降水阈值（单位与 pr 一致）。
        metric_name (str): 指标中文名称，用于日志输出。
        func_name (str): 指标函数名，用于进度条显示。
    """
    pr = check_data(pr)
    # print(f"计算≥{threshold}mm降水{metric_name} ({func_name})")

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue
        threshold_mask = year_data >= threshold
        total = year_data.where(threshold_mask).sum(dim='time')
        days = threshold_mask.sum(dim='time')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            intensity = (total / days).where(days > 0)
        result_list.append(intensity.astype(np.float32))
        year_labels.append(int(year))

    if not result_list:
        return None
    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)


def _calc_threshold_ratio(pr, threshold, metric_name, func_name):
    """
    固定阈值指标通用函数：统计年超阈值降水总量占全年总降水量的比重。

    参数:
        pr (xarray.DataArray): 日降水数据。
        threshold (float): 日降水阈值（单位与 pr 一致）。
        metric_name (str): 指标中文名称，用于日志输出。
        func_name (str): 指标函数名，用于进度条显示。
    """
    pr = check_data(pr)

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue

        threshold_total = year_data.where(year_data >= threshold, 0).sum(dim='time')
        annual_total = year_data.sum(dim='time')

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ratio = (threshold_total / annual_total).where(annual_total > 0, np.nan)

        result_list.append(ratio.astype(np.float32))
        year_labels.append(int(year))

    if not result_list:
        return None

    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)


def R10mm_precipitation(pr):
    """
    逐年日降水量 >= 10 mm 的降水总量（R10p）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_precip(pr, 10.0, '总量', 'R10mm_precipitation')


def R10mm_days(pr):
    """
    逐年日降水量 >= 10 mm 的降水日数（R10d）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_days(pr, 10.0, '日数', 'R10mm_days')


def R10mm_intensity(pr):
    """
    逐年日降水量 >= 10 mm 的降水强度（R10i = 总量 / 日数）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_intensity(pr, 10.0, '强度', 'R10mm_intensity')


def R10mm_ratio(pr):
    """
    逐年日降水量 >= 10 mm 的降水总量占全年总降水量的比重。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    result = _calc_threshold_ratio(pr, 10.0, '比重', 'R10mm_ratio')
    if result is not None:
        result.name = 'R10mm_ratio'
        result.attrs.update({
            'long_name': 'Share of annual precipitation for days with precipitation >= 10 mm',
            'description': 'R10mm_ratio - Ratio of precipitation on days >= 10 mm to annual total precipitation',
            'units': '1',
            'threshold': '10 mm',
            'calculation_method': 'sum(pr on days >= threshold) / sum(pr of the year)',
            'note': 'Multiply by 100 to convert to percentage (%)'
        })
    return result


def R20mm_precipitation(pr):
    """
    逐年日降水量 >= 20 mm 的降水总量（R20p）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_precip(pr, 20.0, '总量', 'R20mm_precipitation')


def R20mm_days(pr):
    """
    逐年日降水量 >= 20 mm 的降水日数（R20d）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_days(pr, 20.0, '日数', 'R20mm_days')


def R20mm_intensity(pr):
    """
    逐年日降水量 >= 20 mm 的降水强度（R20i = 总量 / 日数）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_intensity(pr, 20.0, '强度', 'R20mm_intensity')


def R20mm_ratio(pr):
    """
    逐年日降水量 >= 20 mm 的降水总量占全年总降水量的比重。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    result = _calc_threshold_ratio(pr, 20.0, '比重', 'R20mm_ratio')
    if result is not None:
        result.name = 'R20mm_ratio'
        result.attrs.update({
            'long_name': 'Share of annual precipitation for days with precipitation >= 20 mm',
            'description': 'R20mm_ratio - Ratio of precipitation on days >= 20 mm to annual total precipitation',
            'units': '1',
            'threshold': '20 mm',
            'calculation_method': 'sum(pr on days >= threshold) / sum(pr of the year)',
            'note': 'Multiply by 100 to convert to percentage (%)'
        })
    return result


def R25mm_precipitation(pr):
    """
    逐年日降水量 >= 25 mm 的降水总量（R25p）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_precip(pr, 25.0, '总量', 'R25mm_precipitation')


def R25mm_days(pr):
    """
    逐年日降水量 >= 25 mm 的降水日数（R25d）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_days(pr, 25.0, '日数', 'R25mm_days')


def R25mm_intensity(pr):
    """
    逐年日降水量 >= 25 mm 的降水强度（R25i = 总量 / 日数）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_intensity(pr, 25.0, '强度', 'R25mm_intensity')


def R25mm_ratio(pr):
    """
    逐年日降水量 >= 25 mm 的降水总量占全年总降水量的比重。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    result = _calc_threshold_ratio(pr, 25.0, '比重', 'R25mm_ratio')
    if result is not None:
        result.name = 'R25mm_ratio'
        result.attrs.update({
            'long_name': 'Share of annual precipitation for days with precipitation >= 25 mm',
            'description': 'R25mm_ratio - Ratio of precipitation on days >= 25 mm to annual total precipitation',
            'units': '1',
            'threshold': '25 mm',
            'calculation_method': 'sum(pr on days >= threshold) / sum(pr of the year)',
            'note': 'Multiply by 100 to convert to percentage (%)'
        })
    return result


def R50mm_precipitation(pr):
    """
    逐年日降水量 >= 50 mm 的降水总量（R50p）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_precip(pr, 50.0, '总量', 'R50mm_precipitation')


def R50mm_days(pr):
    """
    逐年日降水量 >= 50 mm 的降水日数（R50d）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_days(pr, 50.0, '日数', 'R50mm_days')


def R50mm_intensity(pr):
    """
    逐年日降水量 >= 50 mm 的降水强度（R50i = 总量 / 日数）。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    return _calc_threshold_intensity(pr, 50.0, '强度', 'R50mm_intensity')


def R50mm_ratio(pr):
    """
    逐年日降水量 >= 50 mm 的降水总量占全年总降水量的比重。

    参数:
        pr (xarray.DataArray): 日降水数据。
    """
    result = _calc_threshold_ratio(pr, 50.0, '比重', 'R50mm_ratio')
    if result is not None:
        result.name = 'R50mm_ratio'
        result.attrs.update({
            'long_name': 'Share of annual precipitation for days with precipitation >= 50 mm',
            'description': 'R50mm_ratio - Ratio of precipitation on days >= 50 mm to annual total precipitation',
            'units': '1',
            'threshold': '50 mm',
            'calculation_method': 'sum(pr on days >= threshold) / sum(pr of the year)',
            'note': 'Multiply by 100 to convert to percentage (%)'
        })
    return result


# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# 先定义 select_baseline_period 函数
def _normalize_baseline_years(baseline_years):
    """
    标准化并校验基准期年份参数。

    参数:
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        tuple[int, int]: (start_year, end_year)。
    """
    if baseline_years is None:
        raise ValueError("baseline_years 不能为空，请显式传入基准期，例如 (1979, 2014)。")

    if not isinstance(baseline_years, (tuple, list)) or len(baseline_years) != 2:
        raise ValueError("baseline_years 必须是长度为2的 tuple/list，例如 (1979, 2014)。")

    start_year = int(baseline_years[0])
    end_year = int(baseline_years[1])
    if start_year > end_year:
        raise ValueError(f"无效基准期: start_year({start_year}) 不能大于 end_year({end_year})")

    return start_year, end_year


def select_baseline_period(data, start_year, end_year):
    """
    选择基准期数据，避免日历格式问题。

    参数:
        data (xarray.DataArray): 包含 time 维的输入数据。
        start_year (int): 基准期起始年（包含）。
        end_year (int): 基准期结束年（包含）。

    返回:
        xarray.DataArray: 筛选后的基准期数据。
    """
    start_year = int(start_year)
    end_year = int(end_year)
    if start_year > end_year:
        raise ValueError(f"无效基准期: start_year({start_year}) 不能大于 end_year({end_year})")

    try:
        # 检查是否有时间维度
        if 'time' not in data.dims:
            raise ValueError("输入数据必须包含'time'维度")

        # 获取年份
        years = data.time.dt.year

        # 创建时间选择掩码
        time_mask = (years >= start_year) & (years <= end_year)

        # 选择数据
        baseline_data = data.isel(time=time_mask)

        # 验证选择结果
        if len(baseline_data.time) == 0:
            raise ValueError(f"未找到{start_year}-{end_year}年的数据")

        selected_years = baseline_data.time.dt.year.values
        actual_start = int(np.min(selected_years))
        actual_end = int(np.max(selected_years))

        if actual_start != start_year or actual_end != end_year:
            print(f"注意：实际选择的年份为{actual_start}-{actual_end}，可能与请求的{start_year}-{end_year}不完全一致")

        print(f"已选择基准期数据: {actual_start}-{actual_end}")
        return baseline_data

    except Exception as e:
        print(f"选择基准期数据时出错: {e}")
        raise

def _calculate_percentile_threshold(baseline_pr, percentile, baseline_years):
    """
    为每个格点单独计算基准期的百分位阈值。

    参数:
        baseline_pr (xarray.DataArray): 用于计算阈值的基准期降水数据。
        percentile (float | int): 百分位值，如 90/95/99。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray: 每个格点的百分位阈值。
    """
    baseline_years = _normalize_baseline_years(baseline_years)

    baseline_pr = check_data(baseline_pr)

    # 筛选基准期数据
    start_year, end_year = baseline_years
    print(f"筛选基准期数据: {start_year}-{end_year}")
    # 使用年份条件选择
    years = baseline_pr.time.dt.year
    time_mask = (years >= start_year) & (years <= end_year)
    print("baseline_pr shape before:", baseline_pr.shape)
    print("years shape:", years.shape)
    print("time_mask shape:", time_mask.shape, "内容:", time_mask)
    baseline_pr = baseline_pr.isel(time=time_mask)

    if len(baseline_pr.time) == 0:
        raise ValueError(f"基准期 {start_year}-{end_year} 没有可用数据。")

    selected_years = baseline_pr.time.dt.year.values
    actual_start = int(np.min(selected_years))
    actual_end = int(np.max(selected_years))
    print(f"已选择基准期数据: {actual_start}-{actual_end}")

    # 1. 筛选湿日（≥1mm）
    wet_days = baseline_pr.where(baseline_pr >= 1.0)

    # 2. 检查每个格点是否有足够的湿日数据
    wet_day_count = wet_days.count(dim='time')
    min_wet_days = 10

    wet_day_count_np = wet_day_count.values

    insufficient_mask = wet_day_count_np < min_wet_days
    insufficient_count = np.sum(insufficient_mask)  # 使用np.sum代替.item()

    if insufficient_count > 0:
        total_grids = wet_day_count_np.size
        insufficient_ratio = insufficient_count / total_grids * 100
        # print(f"注意：有 {insufficient_count} 个格点湿日数据不足（<{min_wet_days}天），占总格点的{insufficient_ratio:.1f}%")

    # 3. 为每个格点单独计算百分位数
    # 在计算百分位阈值时，某些格点可能全部为 NaN，会触发 numpy 的 "All-NaN slice encountered" 警告。
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=RuntimeWarning, message='All-NaN slice encountered')
        warnings.filterwarnings('ignore', category=RuntimeWarning, message='Mean of empty slice')
        threshold_np = wet_days.quantile(
            q=percentile / 100.0,
            dim='time',
            skipna=True,
            method='linear',
            keep_attrs=True
        )

    # 4. 处理没有足够湿日的格点
    if insufficient_count > 0:
        # 创建xarray的DataArray来存储mask
        insufficient_mask_da = xr.DataArray(
            insufficient_mask,
            coords={'lat': threshold_np.lat, 'lon': threshold_np.lon},
            dims=['lat', 'lon']
        )
        threshold_np = threshold_np.where(~insufficient_mask_da, np.nan)

    # 5. 添加属性说明
    threshold_np.attrs.update({
        'long_name': f'{percentile}th percentile threshold of wet day precipitation',
        'units': baseline_pr.attrs.get('units', 'mm/day'),
        'percentile': percentile,
        'baseline_period': f'{baseline_years[0]}-{baseline_years[1]}',
        'wet_day_threshold': '1.0 mm/day',
        'min_wet_days_for_statistics': min_wet_days
    })

    return threshold_np


def _calc_percentile_precip(pr, baseline_pr, percentile, metric_name, func_name, baseline_years):
    """
    计算超过百分位阈值的年降水总量（按格点计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据；为 None 时从 pr 按 baseline_years 提取。
        percentile (float | int): 百分位值，如 90/95/99。
        metric_name (str): 指标中文名，用于日志输出。
        func_name (str): 函数名，用于进度条显示。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 逐年降水总量结果；无有效年份时返回 None。
    """
    pr = check_data(pr)
    baseline_years = _normalize_baseline_years(baseline_years)

    if baseline_pr is None:
        print(f"未提供基准期数据，将从输入数据中提取{baseline_years[0]}-{baseline_years[1]}年作为基准期")
        baseline_pr = select_baseline_period(pr, baseline_years[0], baseline_years[1])

    # 获取阈值
    threshold = _calculate_percentile_threshold(baseline_pr, percentile, baseline_years=baseline_years)

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        year_data = pr.sel(time=pr.time.dt.year == year)

        if len(year_data) < 30:
            continue

        # 湿日条件
        wet_mask = year_data >= 1.0

        threshold_exceed = (year_data > threshold) & wet_mask

        total = (year_data * threshold_exceed).sum(dim='time')

        result_list.append(total.astype(np.float32))
        year_labels.append(int(year))

    if not result_list:
        return None

    result = xr.concat(result_list, dim='year').assign_coords(year=year_labels)

    result.name = f'R{percentile}mm_precipitation'
    return result


def _calc_percentile_days(pr, baseline_pr, percentile, metric_name, func_name, baseline_years):
    """
    计算超过百分位阈值的年降水日数（按格点计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据；为 None 时从 pr 按 baseline_years 提取。
        percentile (float | int): 百分位值，如 90/95/99。
        metric_name (str): 指标中文名，用于日志输出。
        func_name (str): 函数名，用于进度条显示。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 逐年超阈值日数结果；无有效年份时返回 None。
    """
    pr = check_data(pr)
    baseline_years = _normalize_baseline_years(baseline_years)

    # 如果未提供基准期数据，从输入数据中提取指定基准期
    if baseline_pr is None:
        print(f"未提供基准期数据，将从输入数据中提取{baseline_years[0]}-{baseline_years[1]}年作为基准期")
        baseline_pr = select_baseline_period(pr, baseline_years[0], baseline_years[1])

    # 获取每个格点的阈值
    threshold = _calculate_percentile_threshold(baseline_pr, percentile, baseline_years=baseline_years)

    # 统计有效阈值数量
    valid_threshold_mask = ~np.isnan(threshold)
    valid_count = valid_threshold_mask.sum().item()
    total_count = threshold.size

    print(f"计算{percentile}百分位降水{metric_name} ({func_name})")
    print(f"基准期: {threshold.attrs.get('baseline_period', f'{baseline_years[0]}-{baseline_years[1]}')}")
    print(f"有效阈值格点: {valid_count}/{total_count} ({valid_count / total_count * 100:.1f}%)")

    if valid_count == 0:
        print(f"警告：没有有效的阈值数据，无法计算{percentile}百分位降水{metric_name}")
        return None

    # 获取唯一的年份
    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        # 使用年份选择
        year_mask = pr.time.dt.year == year
        year_data = pr.isel(time=year_mask)

        # 检查是否有足够的数据
        if len(year_data) < 30:
            print(f"年份{year}数据点不足({len(year_data)})，跳过")
            continue

        # 湿日条件
        wet_mask = year_data >= 1.0
        # 超过阈值条件 - 只对有效阈值的格点进行计算
        percentile_mask = year_data > threshold

        # 计算年日数（无效格点会自动保持为NaN）
        days = (wet_mask & percentile_mask).sum(dim='time').astype(np.float32)
        result_list.append(days)
        year_labels.append(int(year))

    if not result_list:
        print(f"错误：没有足够的数据计算{percentile}百分位降水{metric_name}")
        return None

    # 合并所有年份的结果
    result = xr.concat(result_list, dim='year').assign_coords(year=year_labels)
    result.name = f'R{percentile}mm_days'

    # 添加详细属性
    result.attrs.update({
        'long_name': f'Annual count of days when daily precipitation > {percentile}th percentile',
        'units': 'days/year',
        'percentile': percentile,
        'baseline_period': threshold.attrs.get('baseline_period', f'{baseline_years[0]}-{baseline_years[1]}'),
        'valid_threshold_cells': int(valid_count),
        'total_cells': int(total_count),
        'threshold_calculation': 'Computed individually for each grid cell',
        'description': f'R{percentile}mm_days - Number of days with precipitation > {percentile}th percentile',
        'wet_day_threshold': '1.0 mm/day',
        'calculation_method': f'Count of days with precipitation > {percentile}th percentile threshold',
        'insufficient_data_handling': 'NaN where threshold is NaN (insufficient wet days in baseline)'
    })

    print(f"{percentile}百分位降水{metric_name}计算完成，共{len(result_list)}年数据")
    return result


def _calc_percentile_intensity(pr, baseline_pr, percentile, metric_name, func_name, baseline_years):
    """
    计算超过百分位阈值的降水平均强度（按格点计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据；为 None 时从 pr 按 baseline_years 提取。
        percentile (float | int): 百分位值，如 90/95/99。
        metric_name (str): 指标中文名，用于日志输出。
        func_name (str): 函数名，用于进度条显示。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 逐年超阈值强度结果；无有效年份时返回 None。
    """
    pr = check_data(pr)
    baseline_years = _normalize_baseline_years(baseline_years)

    # 如果未提供基准期数据，从输入数据中提取指定基准期
    if baseline_pr is None:
        print(f"未提供基准期数据，将从输入数据中提取{baseline_years[0]}-{baseline_years[1]}年作为基准期")
        baseline_pr = select_baseline_period(pr, baseline_years[0], baseline_years[1])

    # 获取每个格点的阈值
    threshold = _calculate_percentile_threshold(baseline_pr, percentile, baseline_years=baseline_years)

    # 统计有效阈值数量
    valid_threshold_mask = ~np.isnan(threshold)
    valid_count = valid_threshold_mask.sum().item()
    total_count = threshold.size

    print(f"计算{percentile}百分位降水{metric_name} ({func_name})")
    print(f"基准期: {threshold.attrs.get('baseline_period', f'{baseline_years[0]}-{baseline_years[1]}')}")
    print(f"有效阈值格点: {valid_count}/{total_count} ({valid_count / total_count * 100:.1f}%)")

    if valid_count == 0:
        print(f"警告：没有有效的阈值数据，无法计算{percentile}百分位降水{metric_name}")
        return None

    # 获取唯一的年份
    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        # 使用年份选择
        year_mask = pr.time.dt.year == year
        year_data = pr.isel(time=year_mask)

        # 检查是否有足够的数据
        if len(year_data) < 30:
            print(f"年份{year}数据点不足({len(year_data)})，跳过")
            continue

        # 湿日条件
        wet_mask = year_data >= 1.0
        # 超过阈值条件 - 只对有效阈值的格点进行计算
        percentile_mask = year_data > threshold

        # 计算超过阈值日子的总降水量
        total = year_data.where(wet_mask & percentile_mask).sum(dim='time')
        # 计算超过阈值日子的天数
        days = (wet_mask & percentile_mask).sum(dim='time')

        # 计算平均强度，避免除以0的警告
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            intensity = (total / days).where(days > 0, np.nan)

        result_list.append(intensity.astype(np.float32))
        year_labels.append(int(year))

    if not result_list:
        print(f"错误：没有足够的数据计算{percentile}百分位降水{metric_name}")
        return None

    # 合并所有年份的结果
    result = xr.concat(result_list, dim='year').assign_coords(year=year_labels)
    result.name = f'R{percentile}mm_intensity'

    # 添加详细属性
    result.attrs.update({
        'long_name': f'Average precipitation intensity on days > {percentile}th percentile',
        'units': pr.attrs.get('units', 'mm/day'),
        'percentile': percentile,
        'baseline_period': threshold.attrs.get('baseline_period', f'{baseline_years[0]}-{baseline_years[1]}'),
        'valid_threshold_cells': int(valid_count),
        'total_cells': int(total_count),
        'threshold_calculation': 'Computed individually for each grid cell',
        'description': f'R{percentile}mm_intensity - Average precipitation on days > {percentile}th percentile',
        'wet_day_threshold': '1.0 mm/day',
        'calculation_method': f'Average precipitation on days > {percentile}th percentile threshold',
        'insufficient_data_handling': 'NaN where threshold is NaN (insufficient wet days in baseline)'
    })

    print(f"{percentile}百分位降水{metric_name}计算完成，共{len(result_list)}年数据")
    return result


def _calc_percentile_total_ratio(pr, baseline_pr, percentile, func_name, baseline_years):
    """
    计算超过百分位阈值降水总量占全年总降水量的比重。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据；为 None 时从 pr 按 baseline_years 提取。
        percentile (float | int): 百分位值，如 90/95/99。
        func_name (str): 函数名，用于进度条显示。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 比重结果（0-1）；无有效年份时返回 None。
    """
    pr = check_data(pr)
    baseline_years = _normalize_baseline_years(baseline_years)

    if baseline_pr is None:
        print(f"未提供基准期数据，将从输入数据中提取{baseline_years[0]}-{baseline_years[1]}年作为基准期")
        baseline_pr = select_baseline_period(pr, baseline_years[0], baseline_years[1])

    threshold = _calculate_percentile_threshold(baseline_pr, percentile, baseline_years=baseline_years)

    years = np.unique(pr.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=func_name):
        year_data = pr.sel(time=pr.time.dt.year == year)
        if len(year_data) < 30:
            continue

        wet_mask = year_data >= 1.0
        exceed_mask = (year_data > threshold) & wet_mask

        exceed_total = (year_data * exceed_mask).sum(dim='time')
        annual_total = year_data.sum(dim='time')

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            # 显式对齐空间坐标，避免基准期与目标数据坐标不完全一致时触发对齐错误
            exceed_total_aligned, annual_total_aligned = xr.align(
                exceed_total,
                annual_total,
                join='inner',
                copy=False
            )
            ratio = xr.where(
                annual_total_aligned > 0,
                exceed_total_aligned / annual_total_aligned,
                np.nan
            )

        result_list.append(ratio.astype(np.float32))
        year_labels.append(int(year))

    if not result_list:
        return None

    return xr.concat(result_list, dim='year').assign_coords(year=year_labels)

# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
# ====================== 百分位阈值降水指数 ======================
def R95mm_precipitation(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 95 百分位降水总量（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_precip(pr, baseline_pr, 95, '总量', 'R95mm_precipitation', baseline_years=baseline_years)


def R95mm_ratio(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 95 百分位超阈值降水总量占全年总降水量的比重（R95mm_ratio）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。

    返回:
        xarray.DataArray | None: 逐年比重结果（0-1）。
    """
    result = _calc_percentile_total_ratio(pr, baseline_pr, 95, 'R95mm_ratio', baseline_years=baseline_years)
    if result is not None:
        result.name = 'R95mm_ratio'
        result.attrs.update({
            'long_name': 'Share of annual precipitation above 95th percentile threshold',
            'description': 'R95mm_ratio - Ratio of precipitation on days > 95th percentile to annual total precipitation',
            'units': '1',
            'percentile': 95,
            'baseline_period': f'{baseline_years[0]}-{baseline_years[1]}' if baseline_years is not None else '',
            'calculation_method': 'sum(pr on days > threshold) / sum(pr of the year)',
            'note': 'Multiply by 100 to convert to percentage (%)'
        })
    return result


def R95mm_days(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 95 百分位降水日数（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_days(pr, baseline_pr, 95, '日数', 'R95mm_days', baseline_years=baseline_years)


def R95mm_intensity(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 95 百分位降水强度（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_intensity(pr, baseline_pr, 95, '强度', 'R95mm_intensity', baseline_years=baseline_years)


def R99mm_precipitation(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 99 百分位降水总量（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_precip(pr, baseline_pr, 99, '总量', 'R99mm_precipitation', baseline_years=baseline_years)


def R99mm_ratio(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 99 百分位超阈值降水总量占全年总降水量的比重（R99mm_ratio）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。

    返回:
        xarray.DataArray | None: 逐年比重结果（0-1）。
    """
    result = _calc_percentile_total_ratio(pr, baseline_pr, 99, 'R99mm_ratio', baseline_years=baseline_years)
    if result is not None:
        result.name = 'R99mm_ratio'
        result.attrs.update({
            'long_name': 'Share of annual precipitation above 99th percentile threshold',
            'description': 'R99mm_ratio - Ratio of precipitation on days > 99th percentile to annual total precipitation',
            'units': '1',
            'percentile': 99,
            'baseline_period': f'{baseline_years[0]}-{baseline_years[1]}' if baseline_years is not None else '',
            'calculation_method': 'sum(pr on days > threshold) / sum(pr of the year)',
            'note': 'Multiply by 100 to convert to percentage (%)'
        })
    return result


def R99mm_days(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 99 百分位降水日数（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_days(pr, baseline_pr, 99, '日数', 'R99mm_days', baseline_years=baseline_years)


def R99mm_intensity(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 99 百分位降水强度（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_intensity(pr, baseline_pr, 99, '强度', 'R99mm_intensity', baseline_years=baseline_years)


# 扩展更多百分位指数（可选）
def R90mm_precipitation(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 90 百分位降水总量（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_precip(pr, baseline_pr, 90, '总量', 'R90mm_precipitation', baseline_years=baseline_years)


def R90mm_ratio(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 90 百分位超阈值降水总量占全年总降水量的比重（R90mm_ratio）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。

    返回:
        xarray.DataArray | None: 逐年比重结果（0-1）。
    """
    result = _calc_percentile_total_ratio(pr, baseline_pr, 90, 'R90mm_ratio', baseline_years=baseline_years)
    if result is not None:
        result.name = 'R90mm_ratio'
        result.attrs.update({
            'long_name': 'Share of annual precipitation above 90th percentile threshold',
            'description': 'R90mm_ratio - Ratio of precipitation on days > 90th percentile to annual total precipitation',
            'units': '1',
            'percentile': 90,
            'baseline_period': f'{baseline_years[0]}-{baseline_years[1]}' if baseline_years is not None else '',
            'calculation_method': 'sum(pr on days > threshold) / sum(pr of the year)',
            'note': 'Multiply by 100 to convert to percentage (%)'
        })
    return result


def R90mm_days(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 90 百分位降水日数（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_days(pr, baseline_pr, 90, '日数', 'R90mm_days', baseline_years=baseline_years)


def R90mm_intensity(pr, baseline_pr=None, baseline_years=None):
    """
    逐年 90 百分位降水强度（基于基准期数据计算阈值）。

    参数:
        pr (xarray.DataArray): 目标时段日降水数据。
        baseline_pr (xarray.DataArray | None): 基准期降水数据。
        baseline_years (tuple[int, int] | list[int, int] | None): 基准期起止年份。
    """
    return _calc_percentile_intensity(pr, baseline_pr, 90, '强度', 'R90mm_intensity', baseline_years=baseline_years)


# ====================== 温度指数 ======================
# ====================== 温度指数 ======================
# ====================== 温度指数 ======================
def check_temperature_data(temp, valid_var_names=None):
    """
    通用温度数据校验函数（含自动时间类型转换）。

    参数:
        temp (xarray.DataArray): 待校验的温度数据，必须包含 time 维。
        valid_var_names (list[str] | tuple[str] | None): 可接受的变量名集合；
            传入 None 时使用内置常用温度变量名。

    返回:
        xarray.DataArray: 校验并转换后的温度数据（time 为 datetime64[D]）。

    异常:
        ValueError: 数据类型、变量名、维度或时间分辨率不符合要求时抛出。
    """
    if not isinstance(temp, xr.DataArray):
        raise ValueError(f"输入数据必须是xarray.DataArray类型，当前类型: {type(temp)}")

    if valid_var_names is None:
        valid_var_names = [
            'tas', 'tasmax', 'tasmin', 'tmax', 'tmin', 'tx', 'tn', 'tg',
            'temperature', 'temp', 't2m'
        ]

    var_name = str(temp.name).lower() if temp.name is not None else ''
    if var_name not in [str(i).lower() for i in valid_var_names]:
        raise ValueError(
            f"无效的温度变量名: '{temp.name}'，支持的变量名: {', '.join(valid_var_names)}"
        )

    if 'time' not in temp.dims:
        raise ValueError("输入数据必须包含'time'维度")

    temp = _convert_time_to_datetime(temp)

    time_vals = temp.time.values
    if len(time_vals) < 2:
        raise ValueError("time维度数据量不足，至少需要2个时间点验证逐日特征")

    time_diff = np.diff(time_vals)
    day_diff = np.timedelta64(1, 'D')
    daily_ratio = np.sum(time_diff == day_diff) / len(time_diff)
    if daily_ratio < 0.95:
        raise ValueError(f"输入数据非逐日数据，1天间隔占比仅{daily_ratio * 100:.1f}%")

    return temp


def _count_days_in_runs(arr, min_run=6):
    """
    统计布尔序列中所有长度 >= min_run 的连续 True 序列总天数。

    参数:
        arr (numpy.ndarray): 一维或高维布尔数组（时间维应在第0维）。
        min_run (int): 连续阈值天数。

    返回:
        numpy.float32 或 numpy.ndarray: 满足条件的总天数。
    """
    if arr.dtype != bool:
        arr = arr.astype(bool)

    def _count_1d(series):
        total_days = 0
        cur_len = 0
        for val in series:
            if val:
                cur_len += 1
            else:
                if cur_len >= min_run:
                    total_days += cur_len
                cur_len = 0
        if cur_len >= min_run:
            total_days += cur_len
        return np.float32(total_days)

    if arr.ndim == 1:
        return _count_1d(arr)

    stacked = np.moveaxis(arr, 0, -1)
    out_shape = stacked.shape[:-1]
    result = np.zeros(out_shape, dtype=np.float32)
    it = np.nditer(result, flags=['multi_index'], op_flags=[['writeonly']])
    while not it.finished:
        idx = it.multi_index
        it[0] = _count_1d(stacked[idx])
        it.iternext()
    return result


def _find_first_run_start(series, min_run=6):
    """
    在一维布尔序列中查找首个长度 >= min_run 的连续 True 序列起始位置。

    参数:
        series (numpy.ndarray): 一维布尔数组。
        min_run (int): 连续阈值天数。

    返回:
        int | None: 起始索引；若不存在返回 None。
    """
    cur_len = 0
    for i, val in enumerate(series):
        if val:
            cur_len += 1
            if cur_len >= min_run:
                return i - min_run + 1
        else:
            cur_len = 0
    return None


def _select_baseline_temperature(temp, baseline_years):
    """
    提取温度指标计算所需基准期数据。

    参数:
        temp (xarray.DataArray): 全时段温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray: 基准期温度数据。
    """
    start_year, end_year = _normalize_baseline_years(baseline_years)
    years = temp.time.dt.year
    baseline = temp.isel(time=(years >= start_year) & (years <= end_year))
    if baseline.time.size == 0:
        raise ValueError(f"基准期 {start_year}-{end_year} 没有可用数据")
    return baseline


def _get_noleap_dayofyear(time_coord):
    """
    将时间坐标映射为 no-leap 日序（1-365）。

    参数:
        time_coord (xarray.DataArray): 时间坐标（通常为 data.time）。

    返回:
        xarray.DataArray: no-leap 日序。
    """
    doy = time_coord.dt.dayofyear
    leap = time_coord.dt.is_leap_year
    month = time_coord.dt.month
    return xr.where(leap & (month > 2), doy - 1, doy)


def _calendar_day_percentile_threshold(temp, baseline_years, percentile, window=5):
    """
    基于日序（dayofyear）和滑动窗口计算温度百分位阈值。

    参数:
        temp (xarray.DataArray): 全时段温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。
        percentile (float | int): 百分位（如 10、90）。
        window (int): 滑动窗口长度（天），推荐奇数。

    返回:
        xarray.DataArray: dayofyear 维度上的阈值场。
    """
    temp = check_temperature_data(temp)
    baseline = _select_baseline_temperature(temp, baseline_years)

    # 去除闰日，避免 dayofyear 在不同年份不可比。
    is_feb29 = (baseline.time.dt.month == 2) & (baseline.time.dt.day == 29)
    baseline = baseline.isel(time=~is_feb29)

    dayofyear = _get_noleap_dayofyear(baseline.time)
    max_doy = 365
    half_window = window // 2
    threshold_list = []

    for doy in range(1, max_doy + 1):
        dist = np.abs(dayofyear - doy)
        circular_dist = xr.where(dist > (max_doy / 2), max_doy - dist, dist)
        mask = circular_dist <= half_window
        window_data = baseline.where(mask, drop=True)

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning)
            q = window_data.quantile(percentile / 100.0, dim='time', skipna=True, method='linear')

        threshold_list.append(q.expand_dims(dayofyear=[doy]))

    threshold = xr.concat(threshold_list, dim='dayofyear')
    threshold.attrs.update({
        'percentile': percentile,
        'baseline_period': f'{baseline_years[0]}-{baseline_years[1]}',
        'window': window,
        'method': 'calendar-day moving window percentile'
    })
    return threshold


def _annual_temperature_count(temp, condition, name):
    """
    逐年统计满足温度条件的日数。

    参数:
        temp (xarray.DataArray): 温度数据。
        condition (callable): 形如 `condition(da) -> bool_da` 的条件函数。
        name (str): 输出变量名。

    返回:
        xarray.DataArray: 年尺度计数结果（单位：days/year）。
    """
    temp = check_temperature_data(temp)
    years = np.unique(temp.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=name):
        year_data = temp.sel(time=temp.time.dt.year == year)
        if year_data.time.size < 30:
            continue
        value = condition(year_data).sum(dim='time').astype(np.float32)
        result_list.append(value)
        year_labels.append(int(year))

    if not result_list:
        return None

    result = xr.concat(result_list, dim='year').assign_coords(year=year_labels)
    result.name = name
    result.attrs.update({'units': 'days/year'})
    return result


def FD(tn):
    """
    FD（霜冻日）：逐年统计 TN < 0°C 的天数。

    参数:
        tn (xarray.DataArray): 日最低温度数据（如变量名 tn/tmin/tasmin）。

    返回:
        xarray.DataArray | None: 年尺度霜冻日数。
    """
    return _annual_temperature_count(tn, lambda da: da < 0.0, 'FD')


def SU(tx):
    """
    SU（夏季日）：逐年统计 TX > 25°C 的天数。

    参数:
        tx (xarray.DataArray): 日最高温度数据（如变量名 tx/tmax/tasmax）。

    返回:
        xarray.DataArray | None: 年尺度夏季日数。
    """
    return _annual_temperature_count(tx, lambda da: da > 25.0, 'SU')


def ID(tx):
    """
    ID（冰冻日）：逐年统计 TX < 0°C 的天数。

    参数:
        tx (xarray.DataArray): 日最高温度数据（如变量名 tx/tmax/tasmax）。

    返回:
        xarray.DataArray | None: 年尺度冰冻日数。
    """
    return _annual_temperature_count(tx, lambda da: da < 0.0, 'ID')


def TR(tn):
    """
    TR（热带夜）：逐年统计 TN > 20°C 的天数。

    参数:
        tn (xarray.DataArray): 日最低温度数据（如变量名 tn/tmin/tasmin）。

    返回:
        xarray.DataArray | None: 年尺度热带夜日数。
    """
    return _annual_temperature_count(tn, lambda da: da > 20.0, 'TR')


def GSL(tg, hemisphere='NH'):
    """
    GSL（生长季长度）。

    参数:
        tg (xarray.DataArray): 日平均温度数据（如变量名 tg/tas/t2m）。
        hemisphere (str): 半球标识，'NH' 表示北半球（自然年），'SH' 表示南半球（7月到次年6月）。

    返回:
        xarray.DataArray | None: 年尺度生长季长度（days/year）。
    """
    tg = check_temperature_data(tg)
    hemisphere = str(hemisphere).upper()
    if hemisphere not in ['NH', 'SH']:
        raise ValueError("hemisphere 仅支持 'NH' 或 'SH'")

    result_list = []
    year_labels = []

    if hemisphere == 'NH':
        years = np.unique(tg.time.dt.year)
        for year in tqdm(years, desc='GSL'):
            y = tg.sel(time=tg.time.dt.year == year)
            if y.time.size < 30:
                continue

            warm_mask = (y > 5.0).values
            start_idx = _find_first_run_start(warm_mask, min_run=6)
            if start_idx is None:
                gsl = xr.full_like(y.isel(time=0), 0).astype(np.float32)
                result_list.append(gsl)
                year_labels.append(int(year))
                continue

            after_july = y.time.dt.month >= 7
            y_after_july = y.isel(time=after_july)
            cold_mask = (y_after_july < 5.0).values
            end_rel_idx = _find_first_run_start(cold_mask, min_run=6)

            if end_rel_idx is None:
                gsl = xr.full_like(y.isel(time=0), np.nan).astype(np.float32)
            else:
                end_idx = int(np.where(after_july.values)[0][0]) + end_rel_idx
                gsl_days = max(0, end_idx - start_idx)
                gsl = xr.full_like(y.isel(time=0), gsl_days).astype(np.float32)

            result_list.append(gsl)
            year_labels.append(int(year))

    else:
        years = np.unique(tg.time.dt.year)
        for year in tqdm(years, desc='GSL'):
            start = np.datetime64(f"{int(year)-1}-07-01")
            end = np.datetime64(f"{int(year)}-06-30")
            y = tg.sel(time=slice(start, end))
            if y.time.size < 300:
                continue

            warm_mask = (y > 5.0).values
            start_idx = _find_first_run_start(warm_mask, min_run=6)
            if start_idx is None:
                gsl = xr.full_like(y.isel(time=0), 0).astype(np.float32)
                result_list.append(gsl)
                year_labels.append(int(year))
                continue

            after_jan = y.time.dt.month <= 6
            y_after_jan = y.isel(time=after_jan)
            cold_mask = (y_after_jan < 5.0).values
            end_rel_idx = _find_first_run_start(cold_mask, min_run=6)

            if end_rel_idx is None:
                gsl = xr.full_like(y.isel(time=0), np.nan).astype(np.float32)
            else:
                end_idx = int(np.where(after_jan.values)[0][0]) + end_rel_idx
                gsl_days = max(0, end_idx - start_idx)
                gsl = xr.full_like(y.isel(time=0), gsl_days).astype(np.float32)

            result_list.append(gsl)
            year_labels.append(int(year))

    if not result_list:
        return None

    result = xr.concat(result_list, dim='year').assign_coords(year=year_labels)
    result.name = 'GSL'
    result.attrs.update({'units': 'days/year'})
    return result


def TXx(tx):
    """
    TXx：月尺度日最高温度的最大值。

    参数:
        tx (xarray.DataArray): 日最高温度数据。

    返回:
        xarray.DataArray: 月尺度最大值序列。
    """
    tx = check_temperature_data(tx)
    result = tx.resample(time='MS').max().astype(np.float32)
    result.name = 'TXx'
    return result


def TNx(tn):
    """
    TNx：月尺度日最低温度的最大值。

    参数:
        tn (xarray.DataArray): 日最低温度数据。

    返回:
        xarray.DataArray: 月尺度最大值序列。
    """
    tn = check_temperature_data(tn)
    result = tn.resample(time='MS').max().astype(np.float32)
    result.name = 'TNx'
    return result


def TXn(tx):
    """
    TXn：月尺度日最高温度的最小值。

    参数:
        tx (xarray.DataArray): 日最高温度数据。

    返回:
        xarray.DataArray: 月尺度最小值序列。
    """
    tx = check_temperature_data(tx)
    result = tx.resample(time='MS').min().astype(np.float32)
    result.name = 'TXn'
    return result


def TNn(tn):
    """
    TNn：月尺度日最低温度的最小值。

    参数:
        tn (xarray.DataArray): 日最低温度数据。

    返回:
        xarray.DataArray: 月尺度最小值序列。
    """
    tn = check_temperature_data(tn)
    result = tn.resample(time='MS').min().astype(np.float32)
    result.name = 'TNn'
    return result


def _temperature_percentile_percentage(temp, baseline_years, percentile, greater_than=True, name=''):
    """
    计算温度相对日序百分位阈值的逐年百分比。

    参数:
        temp (xarray.DataArray): 目标时段温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。
        percentile (float | int): 百分位阈值（10 或 90）。
        greater_than (bool): True 表示统计 `temp > threshold`，False 表示 `temp < threshold`。
        name (str): 输出变量名。

    返回:
        xarray.DataArray | None: 年尺度百分比（%）。
    """
    temp = check_temperature_data(temp)
    threshold = _calendar_day_percentile_threshold(temp, baseline_years, percentile=percentile, window=5)

    is_feb29 = (temp.time.dt.month == 2) & (temp.time.dt.day == 29)
    temp = temp.isel(time=~is_feb29)

    doy = _get_noleap_dayofyear(temp.time)
    threshold_on_time = threshold.sel(dayofyear=doy)

    if greater_than:
        exceed = temp > threshold_on_time
    else:
        exceed = temp < threshold_on_time

    result = (exceed.groupby('time.year').mean(dim='time') * 100.0).astype(np.float32)
    result.name = name
    result.attrs.update({
        'units': '%',
        'percentile': percentile,
        'baseline_period': f'{baseline_years[0]}-{baseline_years[1]}',
        'window': '5-day centered'
    })
    return result


def TN10p(tn, baseline_years=(1961, 1990)):
    """
    TN10p：逐年 TN 小于基准期日序 10 百分位阈值的百分比。

    参数:
        tn (xarray.DataArray): 日最低温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 年尺度百分比（%）。
    """
    return _temperature_percentile_percentage(tn, baseline_years, percentile=10, greater_than=False, name='TN10p')


def TX10p(tx, baseline_years=(1961, 1990)):
    """
    TX10p：逐年 TX 小于基准期日序 10 百分位阈值的百分比。

    参数:
        tx (xarray.DataArray): 日最高温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 年尺度百分比（%）。
    """
    return _temperature_percentile_percentage(tx, baseline_years, percentile=10, greater_than=False, name='TX10p')


def TN90p(tn, baseline_years=(1961, 1990)):
    """
    TN90p：逐年 TN 大于基准期日序 90 百分位阈值的百分比。

    参数:
        tn (xarray.DataArray): 日最低温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 年尺度百分比（%）。
    """
    return _temperature_percentile_percentage(tn, baseline_years, percentile=90, greater_than=True, name='TN90p')


def TX90p(tx, baseline_years=(1961, 1990)):
    """
    TX90p：逐年 TX 大于基准期日序 90 百分位阈值的百分比。

    参数:
        tx (xarray.DataArray): 日最高温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 年尺度百分比（%）。
    """
    return _temperature_percentile_percentage(tx, baseline_years, percentile=90, greater_than=True, name='TX90p')


def _temperature_spell_days(temp, baseline_years, percentile, warm_spell=True, min_run=6, name=''):
    """
    计算温度持续事件（WSDI/CSDI）的逐年总天数。

    参数:
        temp (xarray.DataArray): 目标时段温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。
        percentile (float | int): 百分位阈值（10 或 90）。
        warm_spell (bool): True 表示暖事件（> 阈值），False 表示冷事件（< 阈值）。
        min_run (int): 连续天数阈值。
        name (str): 输出变量名。

    返回:
        xarray.DataArray | None: 年尺度总天数（days/year）。
    """
    temp = check_temperature_data(temp)
    threshold = _calendar_day_percentile_threshold(temp, baseline_years, percentile=percentile, window=5)

    is_feb29 = (temp.time.dt.month == 2) & (temp.time.dt.day == 29)
    temp = temp.isel(time=~is_feb29)
    threshold_on_time = threshold.sel(dayofyear=_get_noleap_dayofyear(temp.time))

    if warm_spell:
        mask = temp > threshold_on_time
    else:
        mask = temp < threshold_on_time

    years = np.unique(temp.time.dt.year)
    result_list = []
    year_labels = []

    for year in tqdm(years, desc=name):
        y_mask = mask.sel(time=mask.time.dt.year == year)
        if y_mask.time.size < 30:
            continue
        days = xr.apply_ufunc(
            _count_days_in_runs,
            y_mask,
            input_core_dims=[['time']],
            output_core_dims=[[]],
            vectorize=True,
            kwargs={'min_run': min_run},
            output_dtypes=[np.float32]
        )
        result_list.append(days)
        year_labels.append(int(year))

    if not result_list:
        return None

    result = xr.concat(result_list, dim='year').assign_coords(year=year_labels)
    result.name = name
    result.attrs.update({
        'units': 'days/year',
        'min_run': min_run,
        'percentile': percentile,
        'baseline_period': f'{baseline_years[0]}-{baseline_years[1]}'
    })
    return result


def WSDI(tx, baseline_years=(1961, 1990)):
    """
    WSDI：逐年暖持续事件总天数（TX > 90 百分位且连续至少 6 天）。

    参数:
        tx (xarray.DataArray): 日最高温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 年尺度总天数（days/year）。
    """
    return _temperature_spell_days(tx, baseline_years, percentile=90, warm_spell=True, min_run=6, name='WSDI')


def CSDI(tn, baseline_years=(1961, 1990)):
    """
    CSDI：逐年冷持续事件总天数（TN < 10 百分位且连续至少 6 天）。

    参数:
        tn (xarray.DataArray): 日最低温度数据。
        baseline_years (tuple[int, int] | list[int, int]): 基准期起止年份。

    返回:
        xarray.DataArray | None: 年尺度总天数（days/year）。
    """
    return _temperature_spell_days(tn, baseline_years, percentile=10, warm_spell=False, min_run=6, name='CSDI')


def DTR(tx, tn):
    """
    DTR：月尺度日较差（TX - TN）的月平均值。

    参数:
        tx (xarray.DataArray): 日最高温度数据。
        tn (xarray.DataArray): 日最低温度数据。

    返回:
        xarray.DataArray: 月尺度日较差。
    """
    tx = check_temperature_data(tx)
    tn = check_temperature_data(tn)
    tx, tn = xr.align(tx, tn, join='inner', copy=False)
    dtr = (tx - tn).resample(time='MS').mean().astype(np.float32)
    dtr.name = 'DTR'
    dtr.attrs.update({'description': 'Monthly mean diurnal temperature range (TX - TN)'})
    return dtr


