# NCtoTIFF 操作文档

## 导入方式

```python
import klimapy as klipy
```

## 调用方式

```python
klipy.Supporting_Tools.nc_to_tiff(
    nc_file="CN05.1_Tmax_1961-2023_daily.nc",
    output_dir="tiff_output",
    clip_extent=(113, 120, 36, 43),
    variable="tmax"
)
```

本文档介绍 `klimapy` 中 `NCtoTIFF` 模块的使用方法，用于将 NetCDF 数据按时间维度裁剪并导出为 GeoTIFF。

## 1. 模块说明

NCtoTIFF 主要用于处理带时间维度的栅格数据，典型流程包括：

1. 读取 NetCDF 文件
2. 按给定经纬度范围裁剪
3. 按时间步逐个导出为 GeoTIFF
4. 输出处理进度与结果统计

当前实现默认导出变量为 tmax，输出文件命名格式为 Tmax_YYYYMMDD.tiff。

## 2. 安装

```bash
pip install klimapy
```

使用本模块通常还需要以下依赖：

```bash
pip install xarray rioxarray geopandas shapely pandas
```

## 3. 输入数据要求

输入 NetCDF 建议满足：

1. 包含 time 维度
2. 包含可写入空间参考的经纬度坐标
3. 包含变量 tmax（当前函数内部固定读取该变量）
4. 空间坐标系可解释为 EPSG:4326（WGS84）

## 4. 主要函数

### 4.1 nc_to_tiff

```python
nc_to_tiff(nc_file, output_dir, clip_extent)
```

参数说明：

1. nc_file：str，输入 NetCDF 文件路径。
2. output_dir：str，输出 GeoTIFF 文件夹路径；若不存在会自动创建。
3. clip_extent：tuple[float, float, float, float]，裁剪范围，格式为 (min_lon, max_lon, min_lat, max_lat)，单位为度。

返回：

1. 无显式返回值，函数执行完成后在 output_dir 下生成 GeoTIFF 文件。

## 5. 快速开始

```python
from yu_pytools.NCtoTIFF import nc_to_tiff

nc_to_tiff(
    nc_file="CN05.1_Tmax_1961-2023_daily.nc",
    output_dir="tiff_output",
    clip_extent=(113, 120, 36, 43),
)
```

## 6. 输出说明

函数将按 time 维逐步输出文件：

1. 文件名示例：Tmax_19610101.tiff
2. 输出数量：与裁剪后 time 长度一致
3. 进度信息：约每 10% 打印一次处理进度

## 7. 常见问题

### 7.1 报错：找不到变量 tmax

原因：当前实现固定读取 ds_clipped['tmax']。

建议：

1. 确认 NetCDF 中变量名为 tmax
2. 或在调用前预处理数据，将目标变量重命名为 tmax

### 7.2 报错：缺少 time 维度

请确认输入数据是时间序列栅格，并包含 time 维。

### 7.3 报错：裁剪后无数据

可能原因：

1. clip_extent 超出数据覆盖范围
2. 经度范围设置顺序错误
3. 纬度范围设置顺序错误

请检查 clip_extent 是否满足 (min_lon, max_lon, min_lat, max_lat)。

### 7.4 报错：缺少空间相关依赖

请安装：xarray、rioxarray、geopandas、shapely、pandas。

## 8. 适用场景

1. 将气候模式或观测 NetCDF 转为 GIS 可直接读取的 GeoTIFF
2. 为栅格制图或遥感分析生成逐日 TIFF 数据
3. 在固定区域内批量裁剪并导出多时次栅格