import numpy as np
import os
import xarray as xr
from tqdm import tqdm
import warnings
from datetime import datetime, timedelta

"""加载 shp 参数并返回融合后的几何对象。"""
def _load_shp_geometry(shp):

    if shp is None:
        return None

    if hasattr(shp, 'geometry'):
        geometry = shp.geometry
        crs = getattr(shp, 'crs', None)
        if crs is not None and str(crs).lower() not in {'epsg:4326', '4326'}:
            geometry = shp.to_crs('EPSG:4326').geometry
        return geometry.union_all() if hasattr(geometry, 'union_all') else geometry.unary_union

    if hasattr(shp, 'geom_type'):
        return shp

    if isinstance(shp, (str, os.PathLike)):
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise ImportError("使用 shp 参数需要安装 geopandas。") from exc

        shp_data = gpd.read_file(shp)
        if shp_data.empty:
            raise ValueError("提供的 shp 文件为空，无法裁剪数据。")

        if shp_data.crs is not None and str(shp_data.crs).lower() not in {'epsg:4326', '4326'}:
            shp_data = shp_data.to_crs('EPSG:4326')

        return shp_data.geometry.union_all() if hasattr(shp_data.geometry, 'union_all') else shp_data.geometry.unary_union

    raise TypeError("shp 参数必须是 shp 文件路径、GeoDataFrame/GeoSeries 或 shapely geometry。")

"""按 shp 范围裁剪 DataArray；未提供 shp 时原样返回。"""
def _clip_data_array_by_shp(data_array, shp=None):
    
    if shp is None or data_array is None:
        return data_array

    if 'lat' not in data_array.coords or 'lon' not in data_array.coords:
        raise ValueError("使用 shp 参数时，数据必须包含 lat 和 lon 坐标。")

    geometry = _load_shp_geometry(shp)
    if geometry is None:
        raise ValueError("无法从 shp 参数中解析出有效几何范围。")

    lat = data_array['lat'].values
    lon = data_array['lon'].values
    lon_grid, lat_grid = np.meshgrid(lon, lat)

    try:
        from shapely import intersects_xy

        mask_values = intersects_xy(geometry, lon_grid, lat_grid)
    except ImportError:
        try:
            from shapely.geometry import Point
        except ImportError as exc:
            raise ImportError("使用 shp 参数需要安装 shapely。") from exc

        mask_values = np.vectorize(
            lambda lon_value, lat_value: geometry.intersects(Point(lon_value, lat_value)),
            otypes=[bool],
        )(lon_grid, lat_grid)

    mask = xr.DataArray(
        mask_values,
        coords={'lat': data_array['lat'], 'lon': data_array['lon']},
        dims=('lat', 'lon'),
    )
    return data_array.where(mask)

# ====================== 区域平均函数 ======================
# ====================== 区域平均函数 ======================
# ====================== 区域平均函数 ======================
# ====================== 区域平均函数 ======================
# ====================== 区域平均函数 ======================
# ====================== 区域平均函数 ======================
def calculate_spatial_mean(data_array, method='arithmetic', include_zeros=False, shp=None):
    """
    计算空间平均值（多种方法）

    参数:
        data_array: xarray DataArray
        method: str，计算方法
            - 'arithmetic': 算术平均
            - 'weighted': 地理加权平均（纬度余弦权重）
            - 'area_weighted': 面积加权平均（考虑网格面积）
        include_zeros: bool，是否包含0值
        shp: optional，shp 文件路径、GeoDataFrame/GeoSeries 或 shapely geometry，用于限定统计范围

    返回:
        float: 空间平均值
    """
    if data_array is None:
        return np.nan

    data_array = _clip_data_array_by_shp(data_array, shp)

    if method == 'arithmetic':
        # 算术平均
        if include_zeros:
            valid_mask = ~np.isnan(data_array.values)
        else:
            valid_mask = (~np.isnan(data_array.values)) & (data_array.values > 0)

        if np.sum(valid_mask) == 0:
            return np.nan

        valid_values = data_array.values[valid_mask]
        return np.mean(valid_values)

    elif method == 'weighted':
        # 地理加权平均（纬度余弦权重）
        return calculate_spatial_weighted_mean(data_array, include_zeros)

    elif method == 'area_weighted':
        # 面积加权平均（考虑网格实际面积）
        if 'lat' not in data_array.dims or 'lon' not in data_array.dims:
            return np.nan

        lat = data_array.lat.values
        lon = data_array.lon.values
        values = data_array.values

        if len(values.shape) != 2:
            return np.nan

        # 计算每个网格的面积（平方米）
        R = 6371000  # 地球半径，单位：米
        dlat = np.abs(np.mean(np.diff(lat))) * np.pi / 180
        dlon = np.abs(np.mean(np.diff(lon))) * np.pi / 180

        # 纬度权重（cos(lat)）
        lat_rad = np.deg2rad(lat)
        area_weights = np.cos(lat_rad)[:, np.newaxis] * np.ones(len(lon))

        # 创建有效数据掩码
        if include_zeros:
            valid_mask = ~np.isnan(values)
        else:
            valid_mask = (~np.isnan(values)) & (values > 0)

        if np.sum(valid_mask) == 0:
            return np.nan

        # 计算面积加权平均
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning)
            weighted_sum = np.nansum(values * area_weights * valid_mask)
            total_weight = np.nansum(area_weights * valid_mask)

        return weighted_sum / total_weight if total_weight > 0 else np.nan

    else:
        raise ValueError(f"不支持的method参数: {method}")


def calculate_spatial_weighted_mean(data_array, include_zeros=False, shp=None):
    """
    计算空间地理加权平均值（使用纬度余弦作为权重）

    参数:
        data_array: xarray DataArray，包含lat和lon维度
        include_zeros: bool，是否包含0值数据，默认False（不考虑0值）
        shp: optional，shp 文件路径、GeoDataFrame/GeoSeries 或 shapely geometry，用于限定统计范围

    返回:
        float: 区域加权平均值
    """
    if data_array is None:
        return np.nan

    data_array = _clip_data_array_by_shp(data_array, shp)

    # 检查是否有空间维度
    if 'lat' not in data_array.dims or 'lon' not in data_array.dims:
        return np.nan

    # 获取数据
    lat = data_array.lat.values
    lon = data_array.lon.values
    values = data_array.values

    # 确保是2D数据
    if len(values.shape) != 2:
        return np.nan

    # 创建纬度权重（cos(lat)）
    lat_rad = np.deg2rad(lat)
    weights_lat = np.cos(lat_rad)

    # 扩展到与数据相同的形状
    weights_2d = weights_lat[:, np.newaxis] * np.ones(len(lon))

    # 创建有效数据掩码
    if include_zeros:
        valid_mask = ~np.isnan(values)  # 包含0值，只排除NaN
    else:
        valid_mask = (~np.isnan(values)) & (values > 0)  # 排除NaN和0值

    # 检查是否有有效数据
    if np.sum(valid_mask) == 0:
        return np.nan

    # 计算加权平均值
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=RuntimeWarning)
        weighted_sum = np.nansum(values * weights_2d * valid_mask)
        total_weight = np.nansum(weights_2d * valid_mask)

    return weighted_sum / total_weight if total_weight > 0 else np.nan
# 为保持向后兼容性，添加别名
weighted_mean = calculate_spatial_weighted_mean
spatial_mean = calculate_spatial_mean