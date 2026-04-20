# klimapy 文档

## 安装

```bash
pip install klimapy
```

## 快速导入

```python
import klimapy as klipy
```

推荐的调用方式是通过子模块访问函数，例如 `klipy.ETCCDI.PRCPTOT(...)`、`klipy.BCSD.BCSD(...)`。

## 模块文档

1. [ETCCDI 操作文档](ETCCDI.md)
2. [CSM 操作文档](CSM.md)
3. [降水变率说明](precipvariability.md)
4. [NCtoTIFF 操作文档](NCtoTIFF.md)
5. [BCSD 操作文档](BCSD.md)
6. [导入与调用快速上手](../import_quickstart.md)

## 说明

1. `ETCCDI.md`：极端气候指数（降水+温度）的输入要求、函数说明与示例。
2. `CSM.md`：空间平均计算（含 shp 范围裁剪）的参数说明与示例。
3. `precipvariability.md`：降水变率计算方法、公式推导与示例。
4. `NCtoTIFF.md`：NetCDF 按时间裁剪并批量导出 GeoTIFF 的参数说明与示例。
5. `BCSD.md`：偏差校正与空间降尺度（BCSD）流程说明、参数解释与使用示例。
6. `../import_quickstart.md`：`import klimapy as klipy` 的导入与调用方法、常见报错排查。
