# Quant Research Core — 公開用ポートフォリオ

**生成AIを活用して設計・開発・検証した、定量リサーチ基盤の取り組みを紹介するリポジトリです。**

> **公開範囲**: 本リポジトリはポートフォリオと小規模な独立デモです。研究用システム本体 `quant-research-core` は非公開です。このデモが本体の実装をそのまま再現しているわけではありません。

## 取り組んだ課題

AIが戦略を提案できても、その検証に未来情報の混入、過剰最適化、再現性の欠如があれば、結果は信用できません。そこで、「良さそうな戦略を量産する」より「誤った検証を通しにくくする」ことを優先した研究基盤を個人開発しています。

金融市場データを扱っていますが、目的は運用実績の宣伝でも売買シグナルの配布でもありません。データの取り扱い、実験の記録、監査可能性、AI出力の検証を重視しています。

## 主な機能・設計

| 領域 | 取り組み |
| --- | --- |
| 時点整合性（PIT） | データの発生日・利用可能日・取得日を区別し、未来情報の参照を防止 |
| 検証設計 | Train / Validation / Test / Holdout の分離、ウォークフォワード検証 |
| バックテスト | 約定タイミング、手数料、スプレッド、スリッページを考慮 |
| 監査 | ルックアヘッド、データリーク、実験条件の不整合を検出 |
| 再現性 | 設定・データ版・ハッシュ・試行結果・監査記録を保存 |
| AI活用 | 複数モデルによる仮説生成やレビューを、決定論的な検証の内側に配置 |
| 品質確認 | 単体・結合・異常系テスト、Windows / Linux 向けCI |

研究用の設計概要は [docs/technical-summary.md](docs/technical-summary.md) を参照してください。

## 実行できる研究パイプライン（推奨デモ）

[examples/research_pipeline_demo.py](examples/research_pipeline_demo.py) は、**仮説・仕様検証から結果保存まで**を1コマンドで追える、合成データ専用の小さな実行例です。旧PITデモより全体像を把握しやすく、外部APIや有料サービスも不要です。

```bash
python examples/research_pipeline_demo.py
```

実行すると、時点整合性のあるデータ参照 → 翌バー始値での模擬約定（費用込み） → 記録されたデータ参照と約定条件の検査 → Train/Test/Holdoutの区間収益率 → JSONレポート保存まで進みます。監査に合格しても結果は `REVIEW_REQUIRED` で、人間の判断が必要です。結果は `artifacts/demo-report.json` に保存されます。

**失敗するケースも体験できます：**

```bash
python examples/research_pipeline_demo.py --inject-leak --out artifacts/leak-report.json
```

意図的に未来データを参照すると監査が `REJECTED` を返し、終了コード2で止まります。壊れたことを確認するためのコマンドです。

このデモの監査は記録済みのアクセスログと約定条件を検査するもので、記録されなかった参照や戦略計算全体の正しさは保証しません。買付手数料は購入株数を減らす形で、売却手数料は現金受取額から差し引いて計上しています。Train/Test/Holdoutは区間別の集計のみで、学習・最適化・統計的有意性の検定は行いません。

このデモは単一銘柄・短期間の合成データを使う**独立した説明用実装**であり、非公開の研究エンジンそのもの、統計的有意性、売買の有効性を証明しません。詳しい手順と限界は [技術概要](docs/technical-summary.md#ミニ研究パイプライン合成データ実行デモ) に記載しています。

## 公開デモ：未来情報を見ないデータ参照

`examples/pit_demo.py` は、時点整合性（Point-in-Time）の考え方を確認するための**標準ライブラリだけで動く独立デモ**です。架空の銘柄・合成データを使用しているため、市場データの再配布は含みません。

```bash
python examples/pit_demo.py
python -m unittest discover -s tests -v
```

このデモは本体のソースコードを抜粋したものではなく、設計上の重要な考え方を第三者が手元で確認できるようにした説明用実装です。

## AI駆動開発における担当範囲

- 課題設定と要求の整理、実験・検証手順の設計
- 生成AIへのタスク分解、作業指示、複数モデルの使い分け
- 生成された実装・レポートのテスト結果や失敗事例の確認
- 不具合の再現条件を整理し、AIを使って改善を反復
- GitHub / CI / Docker などを用いた個人開発ワークフローの運用

**実装の多くは生成AIによる支援を受けています。** 個人開発と外部顧客向けの受託実績は区別しています。自力でのコーディング能力と、AIを活用した開発・検証の経験を混同しないことを重視しています。

## 技術環境

Python、pytest、SQLite、YAML、Git / GitHub、GitHub Actions、Docker、生成AI・LLM API（研究システム本体で使用）。

## 限界と注意事項

- 本体のソースコード・実データ・内部実験結果は、このリポジトリには含めていません。
- この公開デモは実際の売買や投資判断には使用できません。
- バックテストの結果は将来の収益性を保証しません。
- 掲載内容は個人開発の説明であり、受託案件の納品実績を示すものではありません。

---

**English summary:** AI-assisted quantitative research infrastructure focused on point-in-time data integrity, leakage auditing, reproducible experiments, and controlled model-generated hypotheses. This public repository contains a synthetic educational demo, not the private research engine or live-trading software.
