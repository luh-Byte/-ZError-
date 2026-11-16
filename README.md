# 题库总库

把 `github_tiku.zip` 里 6 个 GitHub 公开题库仓库、7 种互不兼容的字段结构，统一成一套可直接使用、可重新导入其他刷题工具的总库。

- 来源包：`D:\资料库大全\Tabbit浏览器\github_tiku.zip`
- 总题数：**29479 题**（原始 32926 条，去重 3447 条）
- 生成时间：2026-11-15

## 目录

| 文件 | 内容 |
|---|---|
| `tiku_master.json` | 全量总库（15 MB），一条记录一道题，字段见下 |
| `tiku_master.csv` | 同内容扁平表（8.6 MB，UTF-8 with BOM，Excel 直接双击可开） |
| `分课程/*.csv` | 17 个课程分表，按课程拆好，只刷某一门课时用这个 |
| `质检报告.md` | 统计、答案归一规则、质量标记数量、已知局限 |
| `索引.json` | 各来源 / 题型 / 课程的题量汇总，给程序读 |
| `仅答案序列_杨pub.json` | 两个只有答案、没有题干的专题数据，无法当题目用，单独留存 |
| `截图题库_焊接结构生产.json` | 2026-11-16 从 45 张屏幕截图整理出的 45 题（单 17 / 多 18 / 判 10），字段同总库，另带 `src_no`（原题号）与 `image`（来源截图） |
| `build/build_tiku.py` | 生成脚本，可直接重跑复现全部产物 |
| `build/import_to_zerror.py` | 导入 ZError 本地题库的脚本（默认干跑，`--apply` 才写库） |
| `build/import_screenshots.py` | 把 `截图题库_焊接结构生产.json` 导入 ZError「焊接结构生产」文件夹（默认干跑，`--apply` 才写库并自动备份 db） |

## 字段

| 字段 | 说明 |
|---|---|
| `qid` | 全局编号 `T000001` 起，去重后连续 |
| `source` | 来源仓库 |
| `course` / `course_raw` | 归一化课程名 / 原始课程标识 |
| `chapter` | 章节；YuanSeen 的题库这里放「学校 / 学期」 |
| `qtype` | `单选` / `多选` / `判断` / `填空` |
| `question` | 题干（已清洗空白与换行） |
| `options` | 选项列表，**不含字母前缀**，`options[0]` 就是 A |
| `answer` | 单选/多选：字母串（`B`、`ACD`）；判断：`正确`/`错误`；填空：答案文本 |
| `answer_raw` | 原始答案表示（`[1]`、`1`、`A`、`正确答案： AC` 等），便于回溯 |
| `dup_count` | 该题在几个来源里重复出现 |
| `flags` | 质量标记，见质检报告第五节 |
| `note` | 原题库自带的解析（少数有） |

## 怎么用

- **只要看一眼 / 改格式**：`tiku_master.csv` 或 `分课程/毛概.csv` 直接 Excel 打开。
- **导入其他刷题工具**：读 `tiku_master.json`，`question` + `options` + `answer` 三件套即可映射；答案字母与 `options` 顺序一一对应。
- **只想用干净的题**：筛掉 `flags` 非空的记录，剩 **28780 题（97.6%）**。
- **要复核跨库答案不一致的题**：筛 `flags` 里含「跨源答案冲突」的 44 条。

## 导入 ZError

ZError 的题库就是它的 SQLite 库 `C:\Users\liuyuhe\AppData\Local\ZError\airesponses.db` 的 `AIResponses` 表。写入口径按程序自带 SQL 对齐：

| 列 | 口径 |
|---|---|
| `Question` | 题干 |
| `Options` | `A. xxx  B. yyy`（两个空格分隔）；判断题/填空题为 NULL |
| `Answer` | **选项文字**而非字母：单选=正确选项原文；多选=各选项文字用 `###` 连接；判断=`正确`/`错误`；填空=答案正文（多空 `###`） |
| `QuestionType` | `single` / `multiple` / `judgement` / `completion` |
| `IsAi` | 0（不是 AI 生成，是题库） |
| `FolderId` / `FolderName` | 按课程分文件夹，`ParentId=0` |

```powershell
# 先看统计（不写库）
python "D:\ZError\题库总库\build\import_to_zerror.py"
# 实际导入（导入前请先复制一份 airesponses.db 当回滚点）
python "D:\ZError\题库总库\build\import_to_zerror.py" --apply
```

已导入 **28863 题**、17 个课程文件夹；跳过 422 条缺答案/缺选项的、3 条答案无法转成选项文字的，课内同题干重复去掉 191 条。

## 截图批次（2026-11-16）

45 张屏幕截图对应《焊接结构生产》一份练习：1–25 题单选、26–40 题多选、41–50 题判断（前 20 张未带题号，序号按截图时间顺序补 `W001`–`W020`）。

- 截图只拍到题干和选项，**没有标注正确答案**；答案按焊接专业知识点逐题判定，`flags` 为 `答案待复核` 的 2 题（W016 焊接电流区间、W029 全选存疑）建议对照教材或老师口径确认。
- 截图上鼠标悬停行会带浅灰底，属于 hover 效果而非答案标记，未据此判定答案。

导入 ZError（独立文件夹「焊接结构生产」，已写入 45 题，库内总 28909 题）：

```powershell
python "D:\ZError\题库总库\build\import_screenshots.py"
python "D:\ZError\题库总库\build\import_screenshots.py" --apply
```

脚本每次 `--apply` 前自动复制 `airesponses.db.bak-时间戳` 作为回滚点，并按题干去重，重复运行不会重复插入。

## 重新生成

```powershell
python "D:\ZError\题库总库\build\build_tiku.py"
```

脚本直接从 zip 取数（临时解压、跑完自清），也可指定已解压目录：

```powershell
python "D:\ZError\题库总库\build\build_tiku.py" "D:\somewhere\github_tiku"
```

## 版本记录

本目录是 git 仓库（`.git` 在本目录内），版本差异只看提交信息，文件名不带版本后缀。

- **纳管**：`README.md`、`质检报告.md`、`索引.json`、`仅答案序列_杨pub.json`、`截图题库_焊接结构生产.json`、`build/build_tiku.py`、`build/import_to_zerror.py`、`build/import_screenshots.py`
- **忽略**：`tiku_master.json`、`tiku_master.csv`、`分课程/` —— 这些都是 `build_tiku.py` 从 zip 重新生成的产物，不重复占版本库空间
- **忽略**：`屏幕截图*.png` —— 题干与选项已全部落进 `截图题库_焊接结构生产.json`，每条记录用 `image` 字段回溯原图

提交信息写明「解决了什么 / 用了什么办法 / 时间 / 验证结果」。

## 注意

- 判断题的 `正确/错误` 是由源数据的 `0/1`、`A/B` 映射而来，映射规则经抽样题干语义确认，**没有全量校验条件**。批量使用前建议先小样本试答。
- 同一道题在不同题库被改写措辞的不会合并；去重只看「题干归一 + 答案」。
- 各来源题库版权归原作者，此处仅作个人学习用途的本地整理。
