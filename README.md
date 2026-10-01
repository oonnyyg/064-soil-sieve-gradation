# 土样筛分分析（soil-sieve-gradation）

纯标准库 Python 工具：批量读取土样干质量、各筛孔留样质量与底盘质量，
输出可复核的级配曲线（CSV）与特征粒径报告（JSON）。

需要 Python 3.12+，无第三方依赖。

## 运行方式

```bash
python -m sieve 输入.json --out 输出目录
```

运行后在输出目录生成：

- `report.json`：每个样本的级配曲线、D10/D30/D60、Cu/Cc，以及无效样本及原因；
- `curves.csv`：所有有效样本的曲线点，列为 `sample_id,aperture_mm,percent_passing`。

退出码：全部样本有效为 `0`；存在无效样本为 `1`（其余样本仍正常输出）；
输入文件无法读取或结构错误为 `2`。

## 输入格式

JSON 文件，顶层为包含 `samples` 数组的对象，输入顺序任意：

```json
{
  "samples": [
    {
      "sample_id": "S1",
      "dry_mass": 1000.0,
      "sieves": [
        {"aperture": 10.0, "retained": 120.0},
        {"aperture": 0.5, "retained": 100.0}
      ],
      "pan": 50.0
    }
  ]
}
```

字段说明：

- `sample_id`：非空字符串，整份输入内必须唯一；
- `dry_mass`：送样干质量（克等任意质量单位，全样本内自洽即可），有限且大于零；
- `sieves`：非空数组；`aperture` 为筛孔尺寸（毫米），必须有限且大于零，
  同一样本内不得重复；`retained` 为该筛孔留样质量，必须有限且非负；
- `pan`：底盘留样质量，必须有限且非负。

## 校验与无效样本规则

- 回收总质量 = 各筛孔留样 + 底盘留样，必须为正；
- 当 `|回收总质量 - 送样干质量| > 送样干质量 × 1%` 时该样本无效
  （恰好等于 1% 视为有效）；
- 重复样本标识、重复/非法筛孔、负质量等均判为无效，原因写入
  `report.json` 的 `invalid_samples`，并打印到标准错误；
- 无效样本不参与输出曲线，但不影响其他样本处理。

## 计算约定

1. 以**回收总质量**（而非送样干质量）归一化。
2. 某筛孔的通过率 =（所有更小筛孔的留样质量 + 底盘质量）/ 回收总质量 × 100%。
3. 曲线按孔径**递增**排列；底盘不作为零孔径曲线点输出。
4. D10、D30、D60 在相邻节点间插值：通过率为线性坐标、`ln(孔径)` 为另一坐标，
   即对孔径取对数后线性插值：
   `ln D = ln D₁ + (P - P₁)/(P₂ - P₁) × (ln D₂ - ln D₁)`。
5. 目标通过率恰好命中节点时取满足条件的最小孔径；目标通过率未被任何相邻
   节点包围时记为 `null` 并附说明，**不作外推**。
6. 不均匀系数 `Cu = D60 / D10`；曲率系数 `Cc = D30² / (D10 × D60)`。
   所需粒径缺失时，对应系数记为 `null`。

## 批处理示例

单个文件：

```bash
python -m sieve examples/input.json --out examples/out
```

在 PowerShell 中批量处理一个目录下的多个 JSON，各自输出到独立目录：

```powershell
Get-ChildItem batches -Filter *.json | ForEach-Object {
    python -m sieve $_.FullName --out ("out\" + $_.BaseName)
}
```

在 bash 中：

```bash
for f in batches/*.json; do
  python -m sieve "$f" --out "out/$(basename "${f%.json}")"
done
```

## 自测

```bash
python -m unittest discover -s tests -v
```

测试覆盖输入校验（重复标识/孔径、非法数值、1% 质量平衡边界）、
通过率排序、半对数插值、命中节点取最小孔径、缺失粒径不外推以及 CLI 退出码。
