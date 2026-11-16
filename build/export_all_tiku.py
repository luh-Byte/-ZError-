# -*- coding: utf-8 -*-
"""从 ZError 本地库导出全量题库: tiku_all.json + tiku_all.csv + 统计打印。"""
import sqlite3, json, csv, io, collections, os

DB = r"C:\Users\liuyuhe\AppData\Local\ZError\airesponses.db"
OUT_DIR = r"D:\ZError\题库总库\打包"

c = sqlite3.connect(DB)
# 只导真题库: IsAi=0(非 AI 生成)、排除默认文件夹(里面是软件自测/随手问的记录)
rows = list(c.execute(
    "SELECT FolderName, QuestionType, Question, Options, Answer FROM AIResponses "
    "WHERE IsAi = 0 AND FolderName <> '默认文件夹' ORDER BY FolderId, Id"))
c.close()

folder_counts = collections.Counter(r[0] for r in rows)
type_counts = collections.Counter(r[1] for r in rows)
print("总条数:", len(rows))
print("文件夹:", len(folder_counts))
for f, n in folder_counts.most_common():
    print("  %-14s %5d" % (f, n))
print("题型:", dict(type_counts))

os.makedirs(OUT_DIR, exist_ok=True)
recs = []
for i, (folder, qtype, question, options, answer) in enumerate(rows, 1):
    recs.append({
        "id": "Z%05d" % i,
        "folder": folder,
        "qtype": qtype,
        "question": question,
        "options": options,
        "answer": answer,
    })

json.dump(recs, io.open(os.path.join(OUT_DIR, "tiku_all.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

with io.open(os.path.join(OUT_DIR, "tiku_all.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "文件夹", "题型", "题干", "选项", "答案"])
    for r in recs:
        w.writerow([r["id"], r["folder"], r["qtype"], r["question"], r["options"] or "", r["answer"]])

print("已写:", os.path.join(OUT_DIR, "tiku_all.json"))
print("已写:", os.path.join(OUT_DIR, "tiku_all.csv"))
