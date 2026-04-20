# klimapy 导入与调用快速上手

这份文档用最短路径教你如何从安装到调用函数。

## 1. 安装

```bash
pip install klimapy
```

如果你在本地源码目录开发，建议先更新到最新代码后再安装：

```bash
pip install -U .
```

## 2. 推荐导入方式

```python
import klimapy as klipy
```

说明：

1. 包名建议写 `klimapy`（小写开头）。
2. 使用 `as klipy` 后，后续调用更简洁。

## 3. 现在可以直接怎么用

当前版本顶层导出的是子模块，所以推荐用：

```python
import klimapy as klipy

# ETCCDI 子模块
fd = klipy.ETCCDI.FD(tn)
r95 = klipy.ETCCDI.R95mm_precipitation(pr, baseline_years=(1981, 2010))

# BCSD 子模块
# result = klipy.BCSD.some_function(...)

# Supporting_Tools 子模块
# out = klipy.Supporting_Tools.some_function(...)
```

## 4. 不能直接这样用的情况

当前默认不建议直接：

```python
klipy.FD(tn)
```

原因：`FD` 在 `ETCCDI` 子模块下，不在顶层命名空间。

## 5. 如果你想直接导入函数

可以按子模块函数导入：

```python
from klimapy.ETCCDI import FD, SU, TN10p, TX90p

fd = FD(tn)
su = SU(tx)
```

这种写法适合脚本里只用少量函数。

## 6. 一个完整最小示例

```python
import xarray as xr
import klimapy as klipy

# 读取示例数据
# 假设 pr/tx/tn/tg 都是日尺度 DataArray，且包含 time 维
pr = xr.open_dataset("pr_daily.nc")["pr"]
tx = xr.open_dataset("tx_daily.nc")["tx"]
tn = xr.open_dataset("tn_daily.nc")["tn"]

# 降水指标
prcptot = klipy.ETCCDI.PRCPTOT(pr)

# 温度指标
fd = klipy.ETCCDI.FD(tn)
tx90p = klipy.ETCCDI.TX90p(tx, baseline_years=(1981, 2010))

# 保存结果
prcptot.to_netcdf("PRCPTOT.nc")
fd.to_netcdf("FD.nc")
tx90p.to_netcdf("TX90p.nc")
```

## 7. 常见报错排查

1. `AttributeError: module 'klimapy' has no attribute 'FD'`
   - 改成 `klipy.ETCCDI.FD(...)`。

2. `No module named klimapy`
   - 先执行 `pip install klimapy`。
   - 或在源码目录执行 `pip install -U .`。

3. 百分位函数报基准期错误
   - 显式传入 `baseline_years=(start, end)`。
   - 确保数据覆盖该年份范围。

## 8. 使用建议

1. 初学者优先用 `import klimapy as klipy` + `klipy.子模块.函数`。
2. 生产脚本建议固定基准期年份，保证结果可比。
3. 温度阈值类指标建议先确认单位为摄氏度。
