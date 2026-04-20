# BCSD 操作文档

## 导入方式

```python
import klimapy as klipy
```

## 调用方式

```python
result = klipy.BCSD.BCSD(
  obs_data_path="/CN05.1nc",
  data_hist_path="/model_historical.nc",
  data_fut_path="model_ssp585.nc",
  output_dir="Output/BCSD",
  model_name="EC-Earth3-Veg_ssp585",
  ref_start_year=1961,
  ref_end_year=2014,
  grid_name="gr"
)
```

本文档介绍 `klimapy` 中 `BCSD` 模块的使用方法，并介绍输入要求、参数说明、函数接口、命令行用法与常见问题。

## 1. 模块说明

BCSD（Bias Correction and Spatial Downscaling）流程分为两步：

1. BC（Bias Correction）：基于观测与模式历史期进行偏差校正。
2. SD（Spatial Downscaling）：将校正结果降尺度到观测网格。

当前实现支持：

1. 历史期 + 未来期 NetCDF 文件输入。
2. 观测网格自动识别，目标分辨率由观测数据本身决定。
3. 按 CMIP 版本自动识别未来情景。

## 2. 输入数据要求

请确保输入文件满足以下要求：

1. 时间维存在（`time` 或 `Time`）。
2. 降水变量可被识别（如 `pr`、`pre`、`precip`、`precipitation`）。
3. 观测数据覆盖参考期（默认 1961-2014，可参数化）。
4. 历史/未来文件为空或路径错误会直接报错。

## 3. 核心函数

### 3.1 BC 函数

```python
def BC(obs_path, gcm_hist_path, gcm_fut_path, model_name, ref_start_year=1961, ref_end_year=2014)
```

参数说明：

1. `obs_path`：观测数据 NetCDF 文件路径。
2. `gcm_hist_path`：模式历史期 NetCDF 文件路径。
3. `gcm_fut_path`：模式未来期 NetCDF 文件路径。
4. `model_name`：模型名，用于日志与输出命名。
5. `ref_start_year`：参考期起始年份。
6. `ref_end_year`：参考期结束年份。

返回说明：

1. 成功返回 `dict`（包含校正后的历史/未来降水、时间/空间坐标信息等）。
2. 失败返回 `None`。

### 3.2 SD 函数

```python
def SD(obs_path, bc_result, output_dir, ref_start_year=1961, ref_end_year=2014, grid_name='gr')
```

参数说明：

1. `obs_path`：观测数据 NetCDF 文件路径。
2. `bc_result`：`BC` 返回的结果字典。
3. `output_dir`：输出目录。
4. `ref_start_year`：参考期起始年份。
5. `ref_end_year`：参考期结束年份。
6. `grid_name`：网格标识，用于输出文件名。

返回说明：

1. 成功返回 `dict`（包含历史/未来 BCSD 输出路径）。
2. 失败返回 `None`。

### 3.3 BCSD 完整流程函数

```python
def BCSD(
    obs_path=None,
    gcm_hist_path=None,
    gcm_fut_path=None,
    model_name=None,
    output_dir=None,
    data_hist_path=None,
    data_fut_path=None,
    obs_data_path=None,
    ref_start_year=1961,
    ref_end_year=2014,
    grid_name='gr'
)
```

参数说明：

1. `obs_path`：观测数据路径（兼容旧参数名）。
2. `gcm_hist_path`：历史期路径（兼容旧参数名）。
3. `gcm_fut_path`：未来期路径（兼容旧参数名）。
4. `model_name`：模型名称；为空时自动由历史文件名推断。
5. `output_dir`：输出目录（必填）。
6. `data_hist_path`：历史期数据文件路径（推荐）。
7. `data_fut_path`：未来期数据文件路径（推荐）。
8. `obs_data_path`：观测数据文件路径（推荐）。
9. `ref_start_year`：参考期起始年份。
10. `ref_end_year`：参考期结束年份。
11. `grid_name`：网格标识（用于输出目录和文件名）。

返回说明：

1. 成功返回 `dict`，包含模型名及历史/未来输出路径。
2. 失败返回 `None`。

说明：

1. 推荐使用 `obs_data_path`、`data_hist_path`、`data_fut_path` 这组新参数。
2. 为兼容历史脚本，旧参数仍可用。

## 4. CMIP 情景映射

函数：

```python
def get_scenarios_by_cmip_version(cmip_version)
```

映射规则：

1. `CMIP6` -> `ssp126`、`ssp245`、`ssp370`、`ssp585`
2. `CMIP5` -> `rcp4.5`、`rcp8.5`

说明：

1. 主程序会按上述规则自动查找未来情景文件。
2. 对 `rcp4.5` 兼容 `rcp45` 命名。

## 5. 命令行用法

脚本入口支持以下参数：

1. `--cmip-version`：CMIP 版本，`CMIP5` 或 `CMIP6`。
2. `--obs-data-path`：观测数据文件路径。
3. `--input-dir`：模式输入目录（包含 `<mode>_<grid>` 子目录）。
4. `--output-dir`：输出目录。
5. `--mode`：模式名称。
6. `--grid-name`：网格标识，默认 `gr`。
7. `--ref-start-year`：参考期起始年份，默认 `1961`。
8. `--ref-end-year`：参考期结束年份，默认 `2014`。

示例（CMIP6）：

```bash
python src/klimapy/BCSD/BCSD.py \
  --cmip-version CMIP6 \
  --obs-data-path "D:/data/CN05.nc" \
  --input-dir "D:/data/Output/01Region/CMIP6" \
  --output-dir "D:/data/Output/02BCSD/CMIP6" \
  --mode "EC-Earth3-Veg" \
  --grid-name gr \
  --ref-start-year 1961 \
  --ref-end-year 2014
```

示例（CMIP5）：

```bash
python src/klimapy/BCSD/BCSD.py \
  --cmip-version CMIP5 \
  --obs-data-path "D:/data/CN05.nc" \
  --input-dir "D:/data/Output/01Region/CMIP5" \
  --output-dir "D:/data/Output/02BCSD/CMIP5" \
  --mode "HadGEM2-ES" \
  --grid-name gr
```

## 6. Python 调用示例

```python
from klimapy.BCSD.BCSD import BCSD

result = BCSD(
    obs_data_path="D:/data/CN05.nc",
    data_hist_path="D:/data/model_historical.nc",
    data_fut_path="D:/data/model_ssp585.nc",
    model_name="EC-Earth3-Veg_ssp585",
    output_dir="D:/data/Output/02BCSD/CMIP6",
    ref_start_year=1961,
    ref_end_year=2014,
    grid_name="gr"
)

print(result)
```

## 7. 输出说明

输出结果包含：

1. 历史期 BCSD 结果文件。
2. 未来期 BCSD 结果文件。

文件命名示例：

1. `{model_name}_{grid_name}_historical_BCSD.nc`
2. `{model_name}_{grid_name}_future_BCSD.nc`

数据属性中会记录：

1. `resolution`：由观测网格自动推断。
2. `reference_period`：参考期。
3. `calendar_type`：日历类型。

## 8. 计算思路与计算方法细节

本节详细解释当前实现中 BCSD 的核心数学与算法流程。

### 8.1 总体流程

BCSD 在实现上是“先校正、后降尺度”的两阶段链路：

1. BC 阶段：在模式粗网格上，构建从 GCM 历史分布到观测分布的传递函数。
2. SD 阶段：将 BC 后的粗网格结果转换到观测高分辨率网格。

可概括为：

1. 观测参考期与 GCM 历史期对齐。
2. 按日序（DOY）进行局地分布映射。
3. 得到 BC 后历史与未来降水场。
4. 用气候态分解和空间插值做尺度细化。

### 8.2 BC 阶段：CDF 分位数映射与传递函数

#### 8.2.1 观测升尺度到模式网格

在构建传递函数前，先将观测数据由高分辨率聚合到 GCM 网格。方法是面积加权平均：

1. 按经纬度坐标计算每个网格的边界。
2. 查找观测网格与目标 GCM 网格重叠区域。
3. 以纬向权重 $w=\cos(\varphi)$ 进行加权。

离散表达式：

$$
P_{coarse} = \frac{\sum (P_{obs} \cdot w)}{\sum (w \cdot I_{valid})}
$$

其中 $I_{valid}$ 为有效值掩膜，确保缺测不参与分母。

#### 8.2.2 日历与时间对齐

当前实现支持多日历并进行对齐：

1. 自动识别 `360_day`、`noleap`、`gregorian`。
2. `noleap` 删除 2 月 29 日。
3. `360_day` 删除每月 31 日。
4. 观测与 GCM 历史按最短共同长度裁剪。

目的：保证同一日序统计样本可比较。

#### 8.2.3 滑动窗口样本构建

对每个网格点、每个 DOY 构建样本窗口：

1. 找到该 DOY 的所有年份索引。
2. 对每个索引取前后 `WINDOW_SIZE` 天（默认 ±15 天）。
3. 分别形成 `obs_window` 与 `gcm_window`。

这样可增加样本量，降低单日噪声。

#### 8.2.4 传递函数构建方法

传递函数由 `create_cdf_spline` 实现，具体步骤：

1. 清理 NaN，并限制降水下界为 0。
2. 计算分位点（默认最多 50 个，实际会按样本量自适应）。
3. 分别求 GCM 与观测的分位值序列。
4. 对 GCM 分位序列做单调修正（避免非递增导致样条异常）。
5. 使用三次平滑样条 `UnivariateSpline(k=3)` 拟合映射关系。

该映射可写为：

$$
P_{obs} = f(P_{gcm})
$$

其中 $f(\cdot)$ 由样条拟合得到。

#### 8.2.5 外推与物理约束

对超出分位拟合区间的输入，采用边界夹持：

1. 小于最小分位值时，映射到观测最小分位值。
2. 大于最大分位值时，映射到观测最大分位值。
3. 结果最终限制为非负，极小值压到 0。

这样可避免外推失稳和负降水。

### 8.3 SD 阶段：气候态分解 + 相对变化插值

#### 8.3.1 观测逐日气候态与 FFT 平滑

先基于观测参考期计算逐日气候态（DOY climatology），再做频域平滑：

1. 对每个 DOY 求多年平均。
2. 对每个网格点的 1 年序列做 FFT。
3. 仅保留 0 频和前 3 个谐波（低频分量）。
4. IFFT 回到时域，得到平滑后的逐日气候态。

这一步保留季节变化主信号，抑制高频噪声。

#### 8.3.2 相对变化因子（Delta Ratio）

在每个时间步：

1. 取 BC 后模式降水切片 $P_{BC}$（粗网格）。
2. 将当天观测气候态粗化到模式网格，得 $C_{obs\_coarse}$。
3. 计算相对变化：

$$
R = \frac{P_{BC}}{C_{obs\_coarse}}
$$

4. 为避免极端比值，对 $R$ 做截断：

$$
R \in [\text{MIN\_RATIO},\ \text{MAX\_RATIO}]
$$

默认区间为 $[0.1, 10.0]$。

#### 8.3.3 具体插值方法

相对变化场从模式网格到观测网格的插值方法为：

1. `scipy.interpolate.RegularGridInterpolator`
2. `method='linear'`（双线性插值）
3. `bounds_error=False`，边界外允许插值器处理

得到高分辨率相对变化 $R_{highres}$ 后，与观测高分辨率气候态相乘：

$$
P_{downscaled} = R_{highres} \cdot C_{obs\_highres}
$$

并最终限制为非负值。

### 8.4 分辨率与目标网格策略

当前版本不再使用固定经纬度步长，而是：

1. 目标网格直接采用观测网格坐标。
2. 输出元数据中的 `resolution` 通过观测坐标差分中位数自动推断。

优点：避免人为设定分辨率与观测网格不一致。

### 8.5 数值稳定性与容错设计

实现中加入了多处稳定性处理：

1. 最小降水阈值 `MIN_PRECIP`，避免除零。
2. 比值上下界 `MIN_RATIO`、`MAX_RATIO`，抑制异常放大。
3. 样本不足时传递函数返回 `None`，回退原值。
4. 插值异常时，单时次回退到气候态场，流程不中断。
5. 对 NaN 做掩膜统计与诊断输出（`DEBUG_CHECK`）。

### 8.6 方法特点与局限

特点：

1. 保留观测空间纹理（通过高分辨率气候态承载）。
2. 保留模式相对变化信号（通过比值场传递）。
3. 对不同日历与文件时间编码具备较强兼容性。

局限：

1. 当前 DOY 采用顺序映射，未基于真实日期逐条匹配。
2. 传递函数按网格点独立构建，未显式建模空间相关误差。
3. 极端尾部映射采用边界夹持，不做额外极值外推模型。

## 9. 常见问题

### 9.1 提示缺少路径参数

请确认传入：

1. 观测路径（`obs_data_path` 或 `obs_path`）。
2. 历史路径（`data_hist_path` 或 `gcm_hist_path`）。
3. 未来路径（`data_fut_path` 或 `gcm_fut_path`）。
4. 输出目录（`output_dir`）。

### 9.2 找不到未来情景文件

请检查：

1. `--cmip-version` 是否正确。
2. 文件名是否包含对应情景关键字。
3. 输入目录是否为 `<mode>_<grid>` 上一级目录。

### 9.3 输出网格与预期不一致

当前逻辑是：

1. 目标网格直接使用观测网格。
2. 分辨率自动由观测坐标推断，不再使用固定经纬度步长。