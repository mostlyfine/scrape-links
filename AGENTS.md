# AIエージェント向けガイド

このドキュメントは、AIエージェントが本スクリプトを効果的に使用するための情報を提供します。

## スクリプト概要

`scrape_links.py`は、Webページを収集してマークダウン形式に変換するツールです。

## 主要機能

### 1. リンク収集

指定されたURL配下のページリンクを再帰的に収集します。

```python
# 実装の要点
def scrape_links(base_url: str, max_depth: int = 0) -> Set[str]:
    # BFS（幅優先探索）で子ページを探索
    # -1で無制限、0以上で深さ制限
```

### 2. 本文抽出

5段階のフォールバック方式（精度優先、カスタマイズ可能）：

```python
def extract_main_content(html_content: str, extractors: Optional[list[str]] = []) -> str:
    # デフォルト: trafilatura → readability → newspaper
    # 最終的に xpath → body が追加される

    # 1. trafilatura: 高速で正確なテキスト抽出（画像・テーブル対応）
    result = extract_by_trafilatura(html_content)
    if result and len(result.strip()) >= MIN_CONTENT_LENGTH: return result

    # 2. readability: 機械学習ベースで本文を抽出
    result = extract_by_readability(html_content)
    if result and len(result.strip()) >= MIN_CONTENT_LENGTH: return result

    # 3. newspaper: NLP強化された記事パース
    result = extract_by_newspaper(html_content)
    if result and len(result.strip()) >= MIN_CONTENT_LENGTH: return result

    # 4. xpath: CSSセレクタで一般的な本文要素を探す
    result = extract_by_xpath(html_content)
    if result and len(result.strip()) >= MIN_CONTENT_LENGTH: return result

    # 5. body: 最終フォールバック
    return extract_by_body(html_content)
```

抽出順序は `-e` オプションでカスタマイズ可能：
```bash
# newspaper を優先的に使用
python scrape_links.py -e newspaper,trafilatura https://example.com/
```

### 3. レート制限

サーバー負荷軽減のための待機処理：

```python
def wait_before_request(max_delay: float = 3.0) -> None:
    """各リクエスト前に1〜max_delay秒のランダム待機"""
    delay = random.uniform(1.0, max_delay)
    logger.debug(f"Waiting {delay:.2f} seconds before request...")
    time.sleep(delay)
```

- **常に有効**: すべてのHTTPリクエスト前に自動実行
- **カスタマイズ可能**: `max_delay` パラメータで最大待ち時間を変更可能
- **デフォルト**: 1〜3秒のランダム待機

### 4. HTML取得

2つの方式をサポート：

```python
def fetch_html_content(url: str, driver: Optional[webdriver.Chrome] = None) -> str:
    """Selenium または requests を使用してHTMLを取得"""
    wait_before_request()

    if driver:
        # Selenium: JavaScript実行後のHTMLを取得
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)  # 追加の待機時間
        return driver.page_source
    else:
        # requests: 静的HTMLを高速取得
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
```

Seleniumの使用：
```bash
# JavaScript でレンダリングされるページに対応
python scrape_links.py --selenium -d 1 -o https://example.com/
```

### 5. マークダウン変換

GFM（GitHub Flavored Markdown）形式で出力：

```python
def html_to_markdown(html_content: str, url: str, extractors: Optional[list[str]] = []) -> str:
    main_content_html = extract_main_content(html_content, extractors)

    h = html2text.HTML2Text()
    h.wrap_links = False        # リンクを折り返さない
    h.wrap_list_items = False   # リストを折り返さない
    h.unicode_snob = True       # Unicode優先
    h.escape_snob = True        # エスケープ最小化
    return h.handle(main_content_html)
```

## エージェントによる使用例

### タスク1: ドキュメント収集

```bash
# 目的: ウェブサイトのドキュメントを収集
# 手順:
# 1. トップページから深さ1で全ページを収集
uvx --from . scrape-links -d 1 -o https://docs.example.com/

# 2. 結果を確認
ls -la output/docs.example.com/
```

### タスク2: 知識ベース構築

```bash
# 目的: 特定トピックの全ページを収集
# 手順:
# 1. 無制限で全ページを収集（レート制限により安全）
uvx --from . scrape-links -d -1 -o -v https://example.com/knowledge/

# 2. ログで進捗を確認
# DEBUG: Waiting 2.34 seconds before request...
# DEBUG: 本文抽出: readability (1234文字)
```

### タスク3: 差分更新

```bash
# 目的: 新しいページのみを追加
# 特徴: --skip-existing で既存ファイルをスキップ（デフォルトは上書き）
uvx --from . scrape-links -d 1 -o -s https://docs.example.com/
# => 既存ファイルはスキップ、新規ファイルのみ保存
```

### タスク4: JavaScript レンダリングが必要なページ

```bash
# 目的: SPAなど JavaScript で動的生成されるコンテンツを取得
# 特徴: Selenium を使用してレンダリング後のHTMLを取得
uvx --from . scrape-links --selenium -d 1 -o https://example.com/app/
# => JavaScript 実行後のHTMLを取得
```

## エージェントが知るべき制約

### 1. 同一ドメイン制限

スクリプトは指定されたURLと同じドメイン内のみを対象とします：

```python
def is_child_path(base_url: str, target_url: str) -> bool:
    # ドメインが異なる場合はFalse
    if base_parsed.netloc != target_parsed.netloc:
        return False
```

### 2. パス階層制限

指定されたURL配下のパスのみを対象とします：

```
https://example.com/docs/guide/ を指定した場合:
✓ https://example.com/docs/guide/page1.html
✓ https://example.com/docs/guide/section/page2.html
✗ https://example.com/docs/other/page.html
✗ https://example.com/blog/
```

### 3. 既存ファイルの扱い

デフォルトでは既存ファイルを上書き。`--skip-existing` オプションでスキップ可能：

```python
def save_page_as_markdown(url: str, html_content: str, output_dir: str = "output",
                         skip_existing: bool = False, extractors: Optional[list[str]] = []) -> None:
    filepath = url_to_filepath(url, output_dir)

    if skip_existing and filepath.exists():
        logger.debug(f"スキップ（既存）: {filepath}")
        return

    # ファイルを保存（上書きまたは新規作成）
```

## 推奨ワークフロー

### ステップ1: 探索

```bash
# まず深さ0でトップページのみを確認
uvx --from . scrape-links https://example.com/docs/
# => リンク数を確認
```

### ステップ2: サンプリング

```bash
# 深さ1で全体の規模を把握
uvx --from . scrape-links -d 1 https://example.com/docs/
# => 見つかったリンク数: 44
```

### ステップ3: 収集

```bash
# 適切な深さで本格収集（レート制限により自動的に適切な間隔で実行）
uvx --from . scrape-links -d 1 -o https://example.com/docs/
```

### ステップ4: 検証

```bash
# 出力を確認
find output -name "*.md" | wc -l
head output/example.com/docs/index.md
```

## デバッグ情報の活用

`-v`オプションで詳細ログが出力されます：

```
DEBUG: スクレイピング開始: https://example.com/docs/
DEBUG: 最大深さ: 1
DEBUG: 取得中 (深さ 0): https://example.com/docs/
DEBUG: Waiting 2.34 seconds before request...
DEBUG: 取得中 (深さ 1): https://example.com/docs/page1.html
DEBUG: Waiting 1.78 seconds before request...
DEBUG: タイトル抽出: h1 = ページタイトル
DEBUG: 本文抽出: readability (1234文字)
DEBUG: 保存完了: output/example.com/docs/page1.md
INFO: 見つかったリンク数: 44
INFO: 保存完了: output/
```

## パフォーマンス考慮事項

### 推奨される深さ設定

- **小規模サイト（<100ページ）**: `-d -1` (無制限)
- **中規模サイト（100-1000ページ）**: `-d 2` または `-d 3`
- **大規模サイト（>1000ページ）**: `-d 1` で段階的に

### リクエスト頻度

現在の実装では順次実行で、各リクエスト間に1〜3秒のランダム待機が自動的に挿入されます。サーバーへの負荷を適切に制御しています。

## エラーハンドリング

### よくあるエラーと対処

1. **タイムアウト**: ネットワーク接続を確認
2. **HTTP 403/404**: URLやアクセス権限を確認
3. **本文抽出失敗**: `-v`でどの抽出方法が使用されたか確認

### ログレベル

- `INFO`: 重要な情報のみ（デフォルト）
- `DEBUG`: 詳細な処理内容（`-v`オプション）
- `WARNING`: 警告（一部ページの失敗など）
- `ERROR`: エラー（実行停止）

## 拡張性

本スクリプトは以下の拡張が可能です：

1. **新しい抽出メソッドの追加**: `extract_by_*`関数を追加
2. **出力形式のカスタマイズ**: `html_to_markdown`を修正
3. **並列処理**: `asyncio`や`concurrent.futures`を使用

## コーディング規約

### 関数ドキュメント（docstring）

**Pythonの関数コメント（docstring）は1行で要約のみを記述すること**

```python
# ✅ 良い例
def fetch_html_content(url: str, driver: Optional[webdriver.Chrome] = None) -> str:
    """Fetch HTML content from a URL using either Selenium or requests."""
    # 実装...

# ❌ 悪い例（複数行の詳細な説明）
def fetch_html_content(url: str, driver: Optional[webdriver.Chrome] = None) -> str:
    """Fetch HTML content from a URL.

    This function supports two methods:
    - Selenium: For JavaScript-rendered pages
    - requests: For static HTML pages

    Args:
        url: The URL to fetch
        driver: Optional Selenium WebDriver instance

    Returns:
        HTML content as string
    """
    # 実装...
```

**理由**:
- コードの可読性を優先
- 関数名とシグネチャで意図が伝わるように設計
- 詳細なドキュメントは必要に応じて別ファイル（README.md、agents.md等）に記載

## テスト方針

### 必須要件

**⚠️ 重要: すべてのコード変更前後で、必ずテストを実行すること**

```bash
# venv環境でテストを実行（必須）
source venv/bin/activate && pytest tests/test_scrape_links.py -v
```

### テスト実行タイミング

1. **コード修正前**: 既存のテストがすべてパスすることを確認
2. **コード修正中**: 関数シグネチャを変更した場合は、影響を受けるテストを即座に修正
3. **コード修正後**: すべてのテストがパスすることを確認
4. **コミット前**: **必ず**すべてのテストがパスすることを確認

### テスト環境

- **必ず venv 環境を使用**: グローバル環境との依存関係の競合を避けるため
- **依存関係の確認**: `requirements.txt` に記載されたすべてのパッケージがインストール済みであること

```bash
# venv環境のセットアップ
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# テストの実行
pytest tests/test_scrape_links.py -v
```

### テスト失敗時の対応

1. **エラーメッセージを確認**: 何が失敗したのかを正確に把握
2. **関数シグネチャの確認**: パラメータの追加・削除により、モック関数のシグネチャが合わなくなっていないか確認
3. **テストの修正**: 必要に応じてテストコードを修正
4. **再実行**: 修正後、すべてのテストがパスすることを確認

### テストカバレッジ

現在のテストは以下をカバーしています：

- URL正規化とパス計算
- コンテンツ抽出（5段階フォールバック）
- マークダウン変換
- リンク収集（深さ制限付き）
- ファイル保存（上書き・スキップ）
- エラーハンドリング

### コミット前チェックリスト

- [ ] venv環境を有効化済み
- [ ] すべてのテストがパス（49/49 passed）
- [ ] 新しい機能に対するテストを追加（必要な場合）
- [ ] コードが正しくフォーマットされている
- [ ] コミットメッセージが Conventional Commits 形式

## まとめ

AIエージェントは以下を理解する必要があります：

- ✅ 深さ0がデフォルト（安全）
- ✅ `-d -1`で無制限収集
- ✅ `-o`でマークダウン保存
- ✅ `-v`で詳細ログ
- ✅ デフォルトは上書き、`-s`（`--skip-existing`）でスキップ
- ✅ ドメイン別にディレクトリ作成
- ✅ 5段階の本文抽出フォールバック（trafilatura → readability → newspaper → xpath → body）
- ✅ `-e`オプションで抽出順序をカスタマイズ可能
- ✅ `--selenium`でJavaScript レンダリング後のHTML取得
- ✅ 自動レート制限（1〜3秒のランダム待機）
