# Klimapy

气候数据分析与处理工具包，面向日尺度气象数据的常见科研流程。

## 1. 项目简介

klimapy 主要用于极端气候指数计算、偏差订正与空间降尺度、空间统计和 NetCDF 栅格处理等任务。

核心特点：

1. 基于 xarray 的多维数据处理流程，便于与现有气候分析代码衔接。
2. 覆盖降水与温度类 ETCCDI 指标。
3. 提供 BCSD、空间平均、NetCDF 到 GeoTIFF 等实用工具。
4. 文档按模块拆分，便于快速查找对应函数和参数。

## 2. 安装

### 从 PyPI 安装

```bash
pip install klimapy
```

### 从源码安装（开发模式）

```bash
pip install -U .
```

## 快速开始

```python
import xarray as xr
import klimapy as klipy

# 读取示例数据
pr = xr.open_dataset("pr_daily.nc")["pr"]
tx = xr.open_dataset("tx_daily.nc")["tx"]
tn = xr.open_dataset("tn_daily.nc")["tn"]

# ETCCDI: 降水指数
prcptot = klipy.ETCCDI.PRCPTOT(pr)

# ETCCDI: 温度指数
fd = klipy.ETCCDI.FD(tn)
tx90p = klipy.ETCCDI.TX90p(tx, baseline_years=(1981, 2010))

# 保存
prcptot.to_netcdf("PRCPTOT.nc")
fd.to_netcdf("FD.nc")
tx90p.to_netcdf("TX90p.nc")
```

说明：

1. 推荐使用 klimapy 小写导入名。
2. 当前版本推荐通过子模块调用函数，例如 klipy.ETCCDI.FD。

## 3. 模块概览

### 3.1 ETCCDI（可计算指标）

ETCCDI 模块全部函数都通过子模块调用，例如：

```python
import klimapy as klipy

# pr: 日降水 DataArray（变量名建议为 pr/pre/precipitation/rain/prec/tp）
# tx: 日最高温 DataArray（变量名建议为 tx/tmax/tasmax）
# tn: 日最低温 DataArray（变量名建议为 tn/tmin/tasmin）
# tg: 日平均温 DataArray（变量名建议为 tg/tas/t2m）
```

#### 3.1.1 基础降水指标：

| 函数      | 指标含义                              | 函数使用方法                       |
| --------- | ------------------------------------- | ---------------------------------- |
| PRCPTOT   | 年总降水量                            | `out = klipy.ETCCDI.PRCPTOT(pr)`   |
| R1mm_days | 年降水日数（日降水 >= 1 mm）          | `out = klipy.ETCCDI.R1mm_days(pr)` |
| SDII      | 简单降水强度（年总降水量 / 年湿日数） | `out = klipy.ETCCDI.SDII(pr)`      |
| RX1DAY    | 年最大 1 日降水量                     | `out = klipy.ETCCDI.RX1DAY(pr)`    |
| RX5DAY    | 年最大连续 5 日降水量                 | `out = klipy.ETCCDI.RX5DAY(pr)`    |
| CDD       | 年最大连续干日数（< 1 mm）            | `out = klipy.ETCCDI.CDD(pr)`       |
| CWD       | 年最大连续湿日数（>= 1 mm）           | `out = klipy.ETCCDI.CWD(pr)`       |

#### 3.1.2 固定阈值降水指标：

| 函数                | 指标含义                                 | 函数使用方法                                 |
| ------------------- | ---------------------------------------- | -------------------------------------------- |
| R10mm_precipitation | 年内 >= 10 mm 降水总量                   | `out = klipy.ETCCDI.R10mm_precipitation(pr)` |
| R10mm_days          | 年内 >= 10 mm 降水日数                   | `out = klipy.ETCCDI.R10mm_days(pr)`          |
| R10mm_intensity     | 年内 >= 10 mm 降水平均强度               | `out = klipy.ETCCDI.R10mm_intensity(pr)`     |
| R10mm_ratio         | 年内 >= 10 mm 降水总量占全年降水总量比重 | `out = klipy.ETCCDI.R10mm_ratio(pr)`         |
| R20mm_precipitation | 年内 >= 20 mm 降水总量                   | `out = klipy.ETCCDI.R20mm_precipitation(pr)` |
| R20mm_days          | 年内 >= 20 mm 降水日数                   | `out = klipy.ETCCDI.R20mm_days(pr)`          |
| R20mm_intensity     | 年内 >= 20 mm 降水平均强度               | `out = klipy.ETCCDI.R20mm_intensity(pr)`     |
| R20mm_ratio         | 年内 >= 20 mm 降水总量占全年降水总量比重 | `out = klipy.ETCCDI.R20mm_ratio(pr)`         |
| R25mm_precipitation | 年内 >= 25 mm 降水总量                   | `out = klipy.ETCCDI.R25mm_precipitation(pr)` |
| R25mm_days          | 年内 >= 25 mm 降水日数                   | `out = klipy.ETCCDI.R25mm_days(pr)`          |
| R25mm_intensity     | 年内 >= 25 mm 降水平均强度               | `out = klipy.ETCCDI.R25mm_intensity(pr)`     |
| R25mm_ratio         | 年内 >= 25 mm 降水总量占全年降水总量比重 | `out = klipy.ETCCDI.R25mm_ratio(pr)`         |
| R50mm_precipitation | 年内 >= 50 mm 降水总量                   | `out = klipy.ETCCDI.R50mm_precipitation(pr)` |
| R50mm_days          | 年内 >= 50 mm 降水日数                   | `out = klipy.ETCCDI.R50mm_days(pr)`          |
| R50mm_intensity     | 年内 >= 50 mm 降水平均强度               | `out = klipy.ETCCDI.R50mm_intensity(pr)`     |
| R50mm_ratio         | 年内 >= 50 mm 降水总量占全年降水总量比重 | `out = klipy.ETCCDI.R50mm_ratio(pr)`         |

#### 3.1.3 百分位阈值降水指标：

说明：以下函数支持 `baseline_pr`（基准期降水）和 `baseline_years`（如 `(1981, 2010)`）。
若 `baseline_pr` 不传，会从 `pr` 中按 `baseline_years` 自动截取；建议显式传入 `baseline_years`。

| 函数                | 指标含义                             | 函数使用方法                                                                                |
| ------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------- |
| R90mm_precipitation | 超过 90 百分位阈值的年降水总量       | `out = klipy.ETCCDI.R90mm_precipitation(pr, baseline_pr=None, baseline_years=(1981, 2010))` |
| R90mm_days          | 超过 90 百分位阈值的年日数           | `out = klipy.ETCCDI.R90mm_days(pr, baseline_pr=None, baseline_years=(1981, 2010))`          |
| R90mm_intensity     | 超过 90 百分位阈值的年平均强度       | `out = klipy.ETCCDI.R90mm_intensity(pr, baseline_pr=None, baseline_years=(1981, 2010))`     |
| R90mm_ratio         | 超过 90 百分位阈值降水总量占全年比重 | `out = klipy.ETCCDI.R90mm_ratio(pr, baseline_pr=None, baseline_years=(1981, 2010))`         |
| R95mm_precipitation | 超过 95 百分位阈值的年降水总量       | `out = klipy.ETCCDI.R95mm_precipitation(pr, baseline_pr=None, baseline_years=(1981, 2010))` |
| R95mm_days          | 超过 95 百分位阈值的年日数           | `out = klipy.ETCCDI.R95mm_days(pr, baseline_pr=None, baseline_years=(1981, 2010))`          |
| R95mm_intensity     | 超过 95 百分位阈值的年平均强度       | `out = klipy.ETCCDI.R95mm_intensity(pr, baseline_pr=None, baseline_years=(1981, 2010))`     |
| R95mm_ratio         | 超过 95 百分位阈值降水总量占全年比重 | `out = klipy.ETCCDI.R95mm_ratio(pr, baseline_pr=None, baseline_years=(1981, 2010))`         |
| R99mm_precipitation | 超过 99 百分位阈值的年降水总量       | `out = klipy.ETCCDI.R99mm_precipitation(pr, baseline_pr=None, baseline_years=(1981, 2010))` |
| R99mm_days          | 超过 99 百分位阈值的年日数           | `out = klipy.ETCCDI.R99mm_days(pr, baseline_pr=None, baseline_years=(1981, 2010))`          |
| R99mm_intensity     | 超过 99 百分位阈值的年平均强度       | `out = klipy.ETCCDI.R99mm_intensity(pr, baseline_pr=None, baseline_years=(1981, 2010))`     |
| R99mm_ratio         | 超过 99 百分位阈值降水总量占全年比重 | `out = klipy.ETCCDI.R99mm_ratio(pr, baseline_pr=None, baseline_years=(1981, 2010))`         |

#### 3.1.4 温度指标：

| 函数  | 指标含义                                        | 函数使用方法                                                |
| ----- | ----------------------------------------------- | ----------------------------------------------------------- |
| FD    | 霜冻日（TN < 0 摄氏度）年日数                   | `out = klipy.ETCCDI.FD(tn)`                                 |
| SU    | 夏季日（TX > 25 摄氏度）年日数                  | `out = klipy.ETCCDI.SU(tx)`                                 |
| ID    | 冰冻日（TX < 0 摄氏度）年日数                   | `out = klipy.ETCCDI.ID(tx)`                                 |
| TR    | 热带夜（TN > 20 摄氏度）年日数                  | `out = klipy.ETCCDI.TR(tn)`                                 |
| GSL   | 生长季长度（默认北半球）                        | `out = klipy.ETCCDI.GSL(tg, hemisphere='NH')`               |
| TXx   | 月尺度日最高温最大值                            | `out = klipy.ETCCDI.TXx(tx)`                                |
| TNx   | 月尺度日最低温最大值                            | `out = klipy.ETCCDI.TNx(tn)`                                |
| TXn   | 月尺度日最高温最小值                            | `out = klipy.ETCCDI.TXn(tx)`                                |
| TNn   | 月尺度日最低温最小值                            | `out = klipy.ETCCDI.TNn(tn)`                                |
| TN10p | TN 低于基准期日序 10 百分位阈值的年百分比       | `out = klipy.ETCCDI.TN10p(tn, baseline_years=(1961, 1990))` |
| TX10p | TX 低于基准期日序 10 百分位阈值的年百分比       | `out = klipy.ETCCDI.TX10p(tx, baseline_years=(1961, 1990))` |
| TN90p | TN 高于基准期日序 90 百分位阈值的年百分比       | `out = klipy.ETCCDI.TN90p(tn, baseline_years=(1961, 1990))` |
| TX90p | TX 高于基准期日序 90 百分位阈值的年百分比       | `out = klipy.ETCCDI.TX90p(tx, baseline_years=(1961, 1990))` |
| WSDI  | 暖持续事件日数（TX > 90 百分位且连续至少 6 天） | `out = klipy.ETCCDI.WSDI(tx, baseline_years=(1961, 1990))`  |
| CSDI  | 冷持续事件日数（TN < 10 百分位且连续至少 6 天） | `out = klipy.ETCCDI.CSDI(tn, baseline_years=(1961, 1990))`  |
| DTR   | 月尺度日较差平均值（TX - TN）                   | `out = klipy.ETCCDI.DTR(tx, tn)`                            |

### 3.2 BCSD
 当前 BCSD 模块仅用于降水变量，可分为“构建传递函数（Bias Correction）+ 插值与空间细化（Spatial Disaggregation）”两步。
##### （1）构建传递函数
传递函数按日序（day-of-year）逐日构建，并采用滑动时间窗增强样本量，具体流程如下：

1. 以目标日序 d 为中心，构建 ±15 天窗口（共 31 天）：

$$
W_d = (k:\ |k-d|\le 15)\quad(\text{按年循环处理日序边界})
$$

2. 在基准期内，将窗口内所有年份的样本拼接，分别形成观测与模式历史样本集合：

$$
S_{\mathrm{obs},d}=(X_{\mathrm{obs}}(y,k):\ y\in Y_0,\ k\in W_d),\quad
S_{\mathrm{mod},d}=(X_{\mathrm{mod,hist}}(y,k):\ y\in Y_0,\ k\in W_d)
$$

3. 基于上述多年窗口样本建立经验分布，并通过光滑三次样条（smoothing cubic spline）拟合单调传递函数。对任意模式值 x，先计算其在模式历史分布中的分位数：

$$
q = F_{\mathrm{mod,hist}}(x)
$$

再映射到观测分布得到订正值：

$$
x_{\mathrm{bc}} = F_{\mathrm{obs,hist}}^{-1}(q)
$$

即整体写为：

$$
X_{\mathrm{bc}} = F_{\mathrm{obs,hist}}^{-1}\left(F_{\mathrm{mod,hist}}(X_{\mathrm{mod}})\right)
$$

在实现上，常将离散分位点对 \((X_{\mathrm{mod},q},X_{\mathrm{obs},q})\) 用光滑三次样条拟合为连续映射函数：

$$
X_{\mathrm{bc}} = T_d\left(X_{\mathrm{mod}}\right),\quad T_d\sim \text{Smoothing Cubic Spline}
$$


##### （2）插值与空间细化
降水场采用比例型订正因子：

$$
X_{\mathrm{bc}} = X_{\mathrm{mod}} \cdot C_q
$$

其中 $C_q$ 来自分位点上的观测-模式比值关系。
先将粗分辨率订正场插值到细网格，常用双线性插值：

$$
X_{\mathrm{bc}}^{\uparrow}(t,i,j) = \sum_{m=1}^{2}\sum_{n=1}^{2} w_{mn}(i,j)\,X_{\mathrm{bc}}(t,I_m,J_n)
$$

其中 $w_{mn}$ 为与相邻 4 个粗网格点距离相关的双线性权重，且 $\sum w_{mn}=1$。

再引入高分辨率气候态构建细化因子：

$$
R(i,j)=\frac{\overline{X}_{\mathrm{obs,fine}}(i,j)}{\overline{X}_{\mathrm{obs,coarse}}^{\uparrow}(i,j)}
$$

最终细网格结果：

$$
X_{\mathrm{fine}}(t,i,j)=X_{\mathrm{bc}}^{\uparrow}(t,i,j)\cdot R(i,j)
$$

说明：当前项目 BCSD 实现未包含温度变量的加性订正与加性细化流程。

### 3.3 Precioitation_Variablity
降水变率，对逐日降水序列先去季节循环，再去趋势：

$$
P'(t)=P(t)-\overline{P}_{\mathrm{doy}}(d)
$$

$$
P''(t)=P'(t)-(at+b)
$$

其中 $\overline{P}_{\mathrm{doy}}(d)$ 是对应年内日序的多年气候平均。

年变率定义为年内标准差：

$$
\sigma_y = \mathrm{std}_{t\in y}\left(P''(t)\right)
$$

变率趋势常用相对趋势（每 10 年百分比）：

$$
Trend_{percent/10a} = (d\sigma/dt) / \sigma_{mean} \times 100 \times 10
$$

### 3.4 Supporting_Tools
#### 3.4.1 CSM
CSM 作用：对格点场在研究区内做空间统计（如算术平均、加权平均）。

CSM 函数与参数：

1. `calculate_spatial_mean(data_array, method='arithmetic', include_zeros=False, shp=None)`
- `data_array`：xarray.DataArray，通常需包含 `lat`、`lon` 维度。
- `method`：统计方法，可选 `arithmetic`、`weighted`、`area_weighted`。
	- `arithmetic`：算术平均。对有效格点直接取平均值。
	- `weighted`：纬度余弦加权平均。使用 cos(lat) 作为权重，降低高纬网格在经纬度网格中的面积偏差影响。
	- `area_weighted`：面积加权平均。按网格面积进行加权（本实现以纬度相关面积权重近似），更接近真实区域平均。
- `include_zeros`：是否将 0 值纳入统计。
	- `False`：仅统计大于 0 且非 NaN 的格点（常用于降水，忽略无降水格点）。
	- `True`：统计所有非 NaN 格点（包括 0 值）。
- `shp`：可选区域范围，支持 shp 路径、GeoDataFrame/GeoSeries 或 shapely geometry。

2. `calculate_spatial_weighted_mean(data_array, include_zeros=False, shp=None)`
- `data_array`：xarray.DataArray，包含 `lat`、`lon`。
- `include_zeros`：是否将 0 值纳入统计。
- `shp`：可选区域范围，同上。

3. 兼容别名：`spatial_mean`、`weighted_mean`。

CSM 示例：

```python
import klimapy as pyt

# 算术平均
v1 = pyt.Supporting_Tools.calculate_spatial_mean(pr.isel(time=0), method='arithmetic')

# 纬度余弦加权平均 + 指定 shp 区域
v2 = pyt.Supporting_Tools.calculate_spatial_weighted_mean(
	pr.isel(time=0),
	include_zeros=False,
	shp='region.shp'
)
```

#### 3.4.2 NCtoTIFF
NCtoTIFF 作用：将 NetCDF 按时间步裁剪并导出为 GeoTIFF，便于 GIS 制图和后处理。

NCtoTIFF 函数与参数：

1. `nc_to_tiff(nc_file, output_dir, clip_extent, variable=None)`
- `nc_file`：输入 NetCDF 文件路径。
- `output_dir`：输出 GeoTIFF 目录（不存在会自动创建）。
- `clip_extent`：裁剪范围 `(min_lon, max_lon, min_lat, max_lat)`，坐标系为 EPSG:4326。
- `variable`：要导出的变量名（如 `pr`、`tas`、`tmax`）。
	- 当为 `None` 时：若 nc 仅有 1 个变量则自动使用。
	- 当 nc 有多个变量时：需显式指定，否则会提示可选变量并报错。

导出前坐标处理：

1. 自动识别并统一经纬度坐标名（兼容 `lon/lat`、`longitude/latitude`、`x/y`）。
2. 自动标准化方向以避免左右/上下翻转：
	 - `lon` 从小到大（西到东）。
	 - `lat` 从大到小（北到南，ArcGIS 常见北向上栅格方向）。

NCtoTIFF 示例：

```python
import klimapy as pyt

pyt.Supporting_Tools.nc_to_tiff(
	nc_file='CN05.1_Tmax_1961-2023_daily.nc',
	output_dir='tiff_output',
	clip_extent=(113, 120, 36, 43),
	variable='tmax'
)
```

说明：

1. 有 `time` 维时按时间逐步导出，文件名示例：`pr_20200101.tiff`。
2. 无 `time` 维时导出单个文件，文件名示例：`pr.tiff`。

## 4 文档导航

完整文档见 docs 目录：

1. docs/ETCCDI.md
2. docs/BCSD.md
3. docs/CSM.md
4. docs/NCtoTIFF.md
5. docs/import_quickstart.md

## 适用场景

1. CMIP 或观测日尺度数据的极端指数批处理。
2. 历史-未来阶段的降水变率与趋势对比分析。
3. NetCDF 数据按时空维度裁剪、统计与导出。

## 联系方式

1. E-mail: yuhaoran251@mails.ucas.ac.cn
   
2. Wechat(username): @余浩然2002
