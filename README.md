# 荐股组合风控监控工作台（GitHub Pages 版）

部门荐股组合的风控监控看板，部署为静态网页，浏览器直接打开即可查看，无需后端。

## 功能

- **总部硬性规则**：累计亏损 ≥ 15% 的标的标红为「强制止损」
- **预警区**：-15% ~ -12% 标黄为「接近止损」
- **技术提示**：收盘价跌破 5 日 / 10 日均线自动提示
- **行情自动更新**：GitHub Actions 每周一至周五 15:30（北京时间）拉取收盘价与日 K，计算 MA5 / MA10 并写入 `quotes.js`
- **数据本地化**：每个访问者的修改（累计涨幅、截图归档）只保存在自己的浏览器 localStorage，不会上传到服务器，也不会影响其他人看到的公开默认数据
- 支持一键导出 / 导入 JSON 备份

## 文件结构

```
index.html                     静态看板主页面（含公开默认持仓数据）
holdings.json                  持仓数据（本次公开版本含 16 个组合）
quotes.js                      每日自动生成的行情数据（window.TDX_QUOTES）
scripts/update_quotes.py       行情抓取脚本（腾讯公开行情接口）
.github/workflows/update-quotes.yml   每日 15:30 自动更新工作流
```

## 部署步骤

1. 在 GitHub 新建一个 **Public** 仓库（例如 `recomm-monitor`），**不要**勾选初始化 README。
2. 在本仓库目录下执行：

```bash
git init
git add .
git commit -m "init: 荐股组合风控监控工作台"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

若使用 HTTPS 推送，需要 GitHub 账号的 **Personal Access Token**（Settings → Developer settings → Personal access tokens → 勾选 `repo`），密码栏填 token。

3. 进入仓库 **Settings → Pages**，Build and deployment 的 Source 选 `Deploy from a branch`，Branch 选 `main`、目录选 `/ (root)`，保存。
4. 约 1 分钟后即可通过 `https://<用户名>.github.io/<仓库名>/` 访问。

## 日常维护

- **每周五收盘后**：由负责人在页面上传各组合截图归档，并按截图更新「累计涨幅」（直接点单元格编辑）。注意：这类修改只保存在操作者本机，若希望全员看到最新数据，请导出 JSON 后更新仓库里的 `index.html` 默认数据并推送。
- **每个交易日 15:30**：GitHub Actions 自动更新行情，无需人工干预（也可在 Actions 页面手动触发）。
- 更换电脑或清理浏览器缓存前，请先点「导出数据」备份。

## 提醒

本公开页面包含部门组合持仓明细，任何拿到链接的人都可查看，请勿将链接转发到外部渠道。如需限制访问，可改用私有仓库 + GitHub Enterprise Pages，或改为部署空模板版本。
