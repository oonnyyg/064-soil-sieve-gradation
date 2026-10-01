# 土样筛分分析（soil sieve gradation）

纯标准库实现的批量土样筛分分析工具：读取各样本的送样干质量、各筛孔留样质量和底盘质量，
输出可复核的级配曲线 CSV 和特征粒径（D10/D30/D60、Cu、Cc）报告 JSON。

需要 Python 3.12+，无第三方依赖。

## 运行方式

```powershell
python -m sieve 输入.json --out 输出目录
```

- 输出目录不存在会自动创建。
- 生成 `report.json`（完整报告）与 `curves.csv`（含样本标识的级配曲线）。
- 存在无效样本时仍输出全部样本结果，进程以非零状态码 `1` 退出；输入文件本身结构错误时退出码为 `2`。

内置自测：

```powershell
python -m sieve --selftest
```

## 输入格式

UTF-8（允许带 BOM）的 JSON，顶层为对象，`samples` 为样本数组（也接受顶层直接为数组）：

```json
{
  "samples": [
    {
      "id": "A-01",
      "dry_mass": 1000.0,
      "pan_mass": 20.0,
      "sieves": [
        {"aperture_mm": 10.0, "retained_mass": 40.0},
        {"aperture_mm": 5.0,  "retained_mass": 90.0},
        {"aperture_mm": 0.075, "retained_mass": 95.0}
      ]
    }
  ]
}
```

字段说明：

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `id` | 样本标识 | 非空字符串，全文件唯一 |
| `dry_mass` | 送样干质量 | 有限、大于 0 |
| `pan_mass` | 底盘（< 最小筛孔）留样质量 | 有限、非负 |
| `sieves[].aperture_mm` | 筛孔孔径，毫米 | 有限、大于 0，同一样本内不重复 |
| `sieves[].retained_mass` | 该筛孔留样质量 | 有限、非负 |

筛孔顺序任意，程序按孔径递增排列；底盘不作为零孔径曲线点。

## 有效性判定

- 回收总质量 = 各筛孔留样质量之和 + 底盘质量，必须为正。
- 当 `|回收总质量 - 送样干质量| > 0.01 × 送样干质量` 时，该样本判为无效
  （即回收差值超过送样质量的 1%）。
- 无效样本在 `report.json` 中列出具体原因（`errors`），不写入 `curves.csv`，
  其他样本照常处理；只要有无效样本，进程退出码为 1。

## 计算约定

1. 以回收总质量 `M` 归一化。对孔径 `dᵢ`（递增排列），其通过率为
   `P(dᵢ) = (底盘质量 + 所有孔径小于 dᵢ 的筛孔留样质量之和) / M × 100%`。
2. 特征粒径 D10/D30/D60：通过率为线性坐标、孔径取对数为另一坐标，
   在相邻曲线节点之间线性插值，即对包围目标通过率的两点
   `(d₁, P₁)`、`(d₂, P₂)`：
   `ln D = ln d₁ + (P - P₁)/(P₂ - P₁) · (ln d₂ - ln d₁)`。
3. 目标通过率恰好命中节点时取该节点孔径；多个节点同率时取最小孔径。
4. 不进行外推：目标通过率超出实测通过率范围或不存在包围区间时，
   相应粒径记为 `null`，并在 `size_notes` 中说明原因。
5. 不均匀系数 `Cu = D60 / D10`；曲率系数 `Cc = D30² / (D10 × D60)`。
   所需粒径缺失（`null`）时，对应系数也为 `null` 并在 `size_notes` 说明。

## 输出说明

`curves.csv` 列：`sample_id, aperture_mm, retained_mass, percent_passing`，
仅包含有效样本，按样本顺序、孔径递增排列。

`report.json` 含统计计数与每个样本的：质量与回收比、曲线点、
`characteristic_sizes`（D10/D30/D60）、`size_notes`、`Cu`、`Cc`，
无效样本则含 `errors`。

## 批处理示例

批量处理目录下多个输入文件（PowerShell），每个输入写入独立输出目录，
任一文件失败可通过退出码感知：

```powershell
Get-ChildItem -Path batches -Filter *.json | ForEach-Object {
    $outDir = Join-Path "results" $_.BaseName
    python -m sieve $_.FullName --out $outDir
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$($_.Name) 含无效样本，请查看 $(Join-Path $outDir 'report.json')"
    }
}
```

仓库自带 `examples/input.json`（含一个回收超差的无效样本），可运行：

```powershell
python -m sieve examples/input.json --out examples/out
```
