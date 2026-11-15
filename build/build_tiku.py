# -*- coding: utf-8 -*-
"""
把 github_tiku 多个来源的题库归一化成一套统一总库。

输入 : 默认从 D:\\资料库大全\\Tabbit浏览器\\github_tiku.zip 直接读取(临时解压, 跑完自清);
       也可用第一个命令行参数指定已解压的 github_tiku 目录。
输出 : D:\\ZError\\题库总库

统一记录字段:
    qid          全局唯一编号
    source       来源仓库
    course       课程名(归一化)
    course_raw   原始课程标识
    chapter      章节(有则填)
    qtype        单选 / 多选 / 判断 / 填空
    question     题干(已清洗)
    options      选项列表(不带字母前缀)
    answer       选择题=字母串; 判断题=正确/错误; 填空=答案文本
    answer_raw   原始答案表示
    flags        质量标记
"""
import io, os, csv, json, re, glob, sys, shutil, tempfile, zipfile, collections

ZIP = r"D:\资料库大全\Tabbit浏览器\github_tiku.zip"
OUT = r"D:\ZError\题库总库"
_TMP = None

def resolve_src():
    """返回可用的题库根目录 github_tiku/"""
    global _TMP
    if len(sys.argv) > 1:
        return os.path.abspath(sys.argv[1])
    _TMP = tempfile.mkdtemp(prefix="tiku_")
    zipfile.ZipFile(ZIP).extractall(_TMP)
    return os.path.join(_TMP, "github_tiku")

SRC = resolve_src()
import atexit
atexit.register(lambda: cleanup())

def cleanup():
    if _TMP and os.path.isdir(_TMP):
        shutil.rmtree(_TMP, ignore_errors=True)


# ---------------------------------------------------------------- 工具函数
WS = re.compile(r"[\s\u00a0\u3000]+")
PUNCT = re.compile(r"[，。、；：？！“”‘’（）()《》<>\[\]【】,.;:?!/\\|_\-—…]+")
LETTER_PREFIX = re.compile(r"^[\s]*[A-HＡ-Ｈ][、.．:：)）]\s*")
BLANK = re.compile(r"[_＿]{2,}|（\s*）|\(\s*\)|【\s*】|＿+")

def clean(s):
    if s is None:
        return ""
    s = str(s).replace("\u00a0", " ").replace("\u3000", " ")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r" +", " ", s)
    return s.strip()

def dedup_key(q, answer):
    """去重键: 题干归一(去空白/标点/填空括号) + 答案"""
    k = PUNCT.sub("", WS.sub("", q))
    k = BLANK.sub("", k)
    k = k.replace("AP", "").lower()
    return (k, WS.sub("", str(answer)).upper())

def strip_prefix(opt):
    return LETTER_PREFIX.sub("", clean(opt))

def parse_lettered(text):
    """从 'A、xxx B、yyy' 里切出选项"""
    ms = list(re.finditer(r"([A-H])、", text))
    if not ms:
        return []
    opts = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        opts.append(clean(text[m.end():end]))
    return opts

def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")

def judge(v, true_vals, false_vals):
    s = WS.sub("", str(v)).upper()
    if s in true_vals:
        return "正确"
    if s in false_vals:
        return "错误"
    return ""

RECS = []
SOURCE_STATS = collections.Counter()

# 课程名归一化: 各来源的课程标识 -> 统一课程名
COURSE_MAP = {
    # CustedNG (convert__index.json 的 id)
    "maogai": "毛概", "makesi": "马原", "jinxiandaishi": "近代史", "sixiu": "思修",
    "clang1": "C语言上", "clang2": "C语言下", "xi": "习概",
    "junli": "军事理论", "junli1": "军事理论", "junli2": "军事理论",
    # YuanSeen (按文件名 tkNNN 绑定, 因源文件 id 字段有重复)
    "tk001": "习概", "tk003": "习概", "tk004": "毛概", "tk005": "马原",
    "tk006": "思修", "tk007": "心理健康", "tk008": "近代史", "tk009": "人工智能",
    "tk010": "入党积极分子", "tk011": "消费者行为学", "tk012": "财务管理",
    "tk014": "政治理论·国省考",
}
SINCE_COURSE = {"CustedNG/tiku_data_generator": "CustedNG", "YuanSeen/TikuJson": "YuanSeen"}

def canon(course_raw, fallback):
    return COURSE_MAP.get(course_raw, fallback)

def clean_options(opts, flags):
    """保留选项位置(中间空串不删, 否则答案字母会错位), 只去掉尾部空项"""
    opts = list(opts or [])
    while opts and not clean(opts[-1]):
        opts = opts[:-1]
    if any(not clean(o) for o in opts):
        flags.append("选项有空缺")
    return [strip_prefix(o) for o in opts]

def add(**kw):
    flags = list(kw.get("flags", []))
    rec = {
        "source": kw["source"],
        "course": kw["course"],
        "course_raw": kw.get("course_raw", ""),
        "chapter": kw.get("chapter", ""),
        "qtype": kw["qtype"],
        "question": clean(kw["question"]),
        "options": clean_options(kw.get("options"), flags),
        "answer": clean(kw.get("answer")).upper() if kw["qtype"] in ("单选", "多选") else clean(kw.get("answer")),
        "answer_raw": kw.get("answer_raw", ""),
        "flags": flags,
    }
    if not rec["question"]:
        return None
    RECS.append(rec)
    SOURCE_STATS[kw["source"]] += 1
    return rec

# ---------------------------------------------------------------- 1. CustedNG
def load_custedng():
    d = os.path.join(SRC, "CustedNG_tiku_data_generator")
    idx = json.loads(read_text(os.path.join(d, "convert__index.json")))
    courses, chapters = {}, {}
    for c in idx.get("content", []):
        courses[c["id"]] = c.get("chinese") or c["id"]
        for ch in c.get("content", []):
            data = os.path.splitext(ch.get("data", ""))[0]
            chapters[(c["id"], data)] = ch.get("title", "")
    for p in sorted(glob.glob(os.path.join(d, "convert__*.json"))):
        fn = os.path.basename(p)
        if any(x in fn for x in ("index", "feedback", "notify", "update", "contributor")):
            continue
        stem = fn[len("convert__"):-len(".json")]
        if "__" not in stem:
            continue
        cid, part = stem.split("__", 1)
        try:
            rows = json.loads(read_text(p))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        course = canon(cid, courses.get(cid, cid))
        chapter = chapters.get((cid, part), "")
        if not chapter and cid == "junli1":
            chapter = "分册 1"
        if not chapter and cid == "junli2":
            chapter = "分册 2"
        for r in rows:
            t = r.get("type")
            q = r.get("question") or r.get("title") or ""
            raw = r.get("answer")
            if t in (0, 1) and isinstance(r.get("options"), list):
                opts = r["options"]
                if t == 0:
                    a = raw if isinstance(raw, int) else (raw[0] if isinstance(raw, list) and raw else None)
                    ans = chr(65 + a) if isinstance(a, int) and 0 <= a < 26 else ""
                    qtype = "单选"
                    if isinstance(a, int) and a >= len(opts):
                        ans = ""
                else:
                    idxs = raw if isinstance(raw, list) else [raw]
                    ans = "".join(chr(65 + i) for i in idxs if isinstance(i, int) and 0 <= i < len(opts))
                    qtype = "多选"
                add(source="CustedNG/tiku_data_generator", course=course, course_raw=cid,
                    chapter=chapter, qtype=qtype, question=q, options=opts,
                    answer=ans, answer_raw=json.dumps(raw, ensure_ascii=False))
            elif t == 3:
                # 源数据把 type:3 混用: 真判断题带「对/错」两选项, 也有 4 选项的单选题混进来
                opts = r.get("options") or []
                v = raw[0] if isinstance(raw, list) and raw else raw
                if len(opts) > 2:
                    ans = chr(65 + v) if isinstance(v, int) and 0 <= v < len(opts) else ""
                    add(source="CustedNG/tiku_data_generator", course=course, course_raw=cid,
                        chapter=chapter, qtype="单选", question=q, options=opts, answer=ans,
                        answer_raw=json.dumps(raw, ensure_ascii=False),
                        flags=["源题型标注为判断,按选项数改判为单选"])
                else:
                    ans, flags = judge(v, {"0"}, {"1"}), []
                    if ans == "" and isinstance(v, int) and v > 1:
                        # 答案索引指向第3+项却没有选项, 源数据丢了选项, 无法还原
                        add(source="CustedNG/tiku_data_generator", course=course, course_raw=cid,
                            chapter=chapter, qtype="单选", question=q, options=[],
                            answer="", answer_raw=json.dumps(raw, ensure_ascii=False),
                            flags=["选项缺失,答案索引无法还原"])
                        continue
                    if ans == "":
                        flags = ["源标注无答案" if v in (-1, "-1") else "判断题答案未识别"]
                    add(source="CustedNG/tiku_data_generator", course=course, course_raw=cid,
                        chapter=chapter, qtype="判断", question=q, options=[],
                        answer=ans, answer_raw=json.dumps(raw, ensure_ascii=False), flags=flags)
            elif t == 2:
                texts = raw if isinstance(raw, list) else [raw]
                add(source="CustedNG/tiku_data_generator", course=course, course_raw=cid,
                    chapter=chapter, qtype="填空", question=q, options=[],
                    answer=" / ".join(clean(x) for x in texts if clean(x)),
                    answer_raw=json.dumps(raw, ensure_ascii=False))

# ---------------------------------------------------------------- 2. YuanSeen
def load_yuanseen():
    d = os.path.join(SRC, "YuanSeen_TikuJson")
    banks = {}
    p = os.path.join(d, "availableBanks.json")
    if os.path.exists(p):
        for b in json.loads(read_text(p)):
            banks[b["id"]] = b
    for f in sorted(glob.glob(os.path.join(d, "json_tk*.json"))):
        o = json.loads(read_text(f))
        # 源文件的 "id" 字段有重复(多个不同题库都写成 tk005), 改用文件名绑定
        bid = os.path.basename(f)[len("json_"):-len(".json")]
        meta = banks.get(bid, {})
        course = canon(bid, (meta.get("title") or bid).strip("《》"))
        sub = meta.get("subject", "")
        chapter = meta.get("description", "")
        tk = o.get("tiku", {})
        for sec, rows in tk.items():
            if not isinstance(rows, list):
                continue
            for r in rows:
                stem = r.get("stem") or ""
                if sec == "danxuan":
                    opts = [r.get("op" + x, "") for x in "abcdef"]
                    add(source="YuanSeen/TikuJson", course=course, course_raw=bid,
                        chapter=" / ".join(x for x in (sub, chapter) if x),
                        qtype="单选", question=stem, options=opts, answer=r.get("answer", ""),
                        answer_raw=r.get("answer", ""))
                elif sec == "duoxuan":
                    opts = [r.get("op" + x, "") for x in "abcdef"]
                    add(source="YuanSeen/TikuJson", course=course, course_raw=bid,
                        chapter=" / ".join(x for x in (sub, chapter) if x),
                        qtype="多选", question=stem, options=opts, answer=r.get("answer", ""),
                        answer_raw=r.get("answer", ""))
                elif sec == "panduan":
                    add(source="YuanSeen/TikuJson", course=course, course_raw=bid,
                        chapter=" / ".join(x for x in (sub, chapter) if x),
                        qtype="判断", question=stem, options=[],
                        answer=judge(r.get("answer", ""), {"A", "T", "正确", "对"}, {"B", "F", "错误", "错"}),
                        answer_raw=r.get("answer", ""))

# ---------------------------------------------------------------- 3. lolisaikou
def load_lolisaikou():
    p = os.path.join(SRC, "lolisaikou_tiku-autoupdate", "questions.json")
    rows = json.loads(read_text(p))
    mapping = {"单选题": "单选", "多选题": "多选", "填空题": "填空", "挑战题": "单选"}
    for r in rows:
        cat = r.get("category", "")
        qtype = mapping.get(cat, "单选")
        opts = r.get("options") or []
        ans = r.get("answer", "")
        flags = []
        if qtype == "填空":
            opts = []
        else:
            ans = WS.sub("", str(ans)).upper()
            if not ans and opts:
                flags.append("缺答案")
        notes = clean(r.get("notes", ""))
        rec = add(source="lolisaikou/tiku-autoupdate", course="通用·安全与素养",
                  course_raw=cat, chapter="", qtype=qtype,
                  question=r.get("content", ""), options=opts, answer=ans,
                  answer_raw=str(r.get("answer", "")), flags=flags)
        if rec is not None and notes:
            rec["note"] = notes

# ---------------------------------------------------------------- 4. li-butter
def load_libutter():
    p = os.path.join(SRC, "li-butter_tiku", "大学生恋爱与性健康题库.json")
    for r in json.loads(read_text(p)):
        opts = [r.get("选项" + x, "") for x in "ABCD"]
        add(source="li-butter/tiku", course="恋爱与性健康", course_raw="",
            chapter="", qtype="单选", question=r.get("题干", ""), options=opts,
            answer=r.get("答案", ""), answer_raw=r.get("答案", ""))

# ---------------------------------------------------------------- 5. SoraNoNeko
def load_sora():
    p = os.path.join(SRC, "SoraNoNeko_cpu_QA", "题库.csv")
    rows = list(csv.reader(io.StringIO(read_text(p))))
    for r in rows:
        if len(r) < 6:
            continue
        stem = clean(r[0])
        diff = ""
        tag = re.search(r"([易中难])$", stem)
        if tag:
            diff = tag.group(1)
            stem = stem[:tag.start()].strip()
        add(source="SoraNoNeko/cpu_QA", course="思政·综合", course_raw="",
            chapter=("难度:" + diff) if diff else "", qtype="单选",
            question=stem, options=[r[1], r[2], r[3], r[4]], answer=r[5],
            answer_raw=r[5])

# ---------------------------------------------------------------- 6. SWERecker
def load_swer():
    p = os.path.join(SRC, "SWERecker_QuestionQueryScript", "all.csv")
    rows = list(csv.reader(io.StringIO(read_text(p))))
    for r in rows:
        if len(r) < 4 or r[0] == "序号":
            continue
        stem = clean(r[1])
        opts = parse_lettered(clean(r[2]))
        body = clean(r[3]).replace("正确答案", "").replace("：", "").strip()
        if not opts and re.search(r"[√✓✔×✗✘Xx]", body):
            ans = "正确" if re.search(r"[√✓✔]", body) else "错误"
            qtype = "判断"
        else:
            ans = re.sub(r"[^A-Ha-h]", "", body).upper()
            qtype = "单选" if len(ans) <= 1 else "多选"
        add(source="SWERecker/QuestionQueryScript", course="思政·综合", course_raw="",
            chapter="", qtype=qtype, question=stem, options=opts, answer=ans,
            answer_raw=r[3])

# ---------------------------------------------------------------- 7. Yangpub(仅答案序列)
def load_yangpub():
    d = os.path.join(SRC, "Yangpub_TiKu")
    extra = {}
    for fn in ("special.json", "weekly.json"):
        p = os.path.join(d, fn)
        if os.path.exists(p):
            extra[fn] = json.loads(read_text(p))
    return extra

# ---------------------------------------------------------------- 主流程
for fn in (load_custedng, load_yuanseen, load_lolisaikou, load_libutter, load_sora, load_swer):
    before = len(RECS)
    fn()
    print("  %-16s +%d" % (fn.__name__, len(RECS) - before))
yangpub = load_yangpub()

# 去重
PRIORITY = {"CustedNG/tiku_data_generator": 0, "YuanSeen/TikuJson": 1,
            "lolisaikou/tiku-autoupdate": 2, "li-butter/tiku": 3,
            "SoraNoNeko/cpu_QA": 4, "SWERecker/QuestionQueryScript": 5}
RECS.sort(key=lambda r: PRIORITY.get(r["source"], 9))

kept, seen, dup_conflict = [], {}, 0
for r in RECS:
    key = dedup_key(r["question"], r["answer"] if r["qtype"] != "填空" else "")
    if key in seen:
        first = seen[key]
        if r["answer"] and first["answer"] and r["answer"] != first["answer"]:
            dup_conflict += 1
            first.setdefault("conflicts", []).append(
                {"source": r["source"], "answer": r["answer"]})
        first.setdefault("dup_count", 1)
        first["dup_count"] += 1
        continue
    seen[key] = r
    kept.append(r)

# 编号
for i, r in enumerate(kept, 1):
    r["qid"] = "T%06d" % i

# 题型改判: 标成单选但答案是多字母的, 实际是多选
for r in kept:
    if r["qtype"] == "单选" and len(r["answer"]) > 1:
        r["qtype"] = "多选"
        r["flags"].append("按答案改判为多选")

# 质检标记
for r in kept:
    n_opt = len(r["options"])
    if r["qtype"] in ("单选", "多选"):
        if not r["options"] and "选项缺失,答案索引无法还原" not in r["flags"]:
            r["flags"].append("无选项")
        if not r["answer"]:
            if "缺答案" not in r["flags"]:
                r["flags"].append("缺答案")
        else:
            bad = any(ch not in "ABCDEFGH"[:n_opt] for ch in r["answer"])
            if bad:
                keep_ans = "".join(ch for ch in r["answer"] if ch in "ABCDEFGH"[:n_opt])
                if keep_ans and r["qtype"] == "多选":
                    r["flags"].append("答案超出选项数已截断")
                    r["answer_full_raw"] = r["answer"]
                    r["answer"] = keep_ans
                else:
                    r["flags"].append("答案超范围")
        if r["qtype"] == "单选" and len(r["answer"]) > 1:
            r["flags"].append("单选多答案")
        if r["qtype"] == "多选" and len(r["answer"]) == 1:
            r["flags"].append("多选单答案")
    if r["qtype"] == "判断" and r["answer"] not in ("正确", "错误"):
        if not any(f in r["flags"] for f in ("源标注无答案", "缺答案")):
            r["flags"].append("缺答案" if not r["answer_raw"].strip() else "判断题答案未识别")
    if "conflicts" in r:
        r["flags"].append("跨源答案冲突")

os.makedirs(OUT, exist_ok=True)
COURSE_DIR = os.path.join(OUT, "分课程")
if os.path.isdir(COURSE_DIR):
    for f in os.listdir(COURSE_DIR):          # 清掉上一轮残留的分册, 避免课程名改名后留旧文件
        if f.lower().endswith(".csv"):
            os.remove(os.path.join(COURSE_DIR, f))
os.makedirs(COURSE_DIR, exist_ok=True)

json.dump(kept, io.open(os.path.join(OUT, "tiku_master.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# CSV
COLS = ["qid", "source", "course", "chapter", "qtype", "question",
        "A", "B", "C", "D", "E", "F", "answer", "answer_raw", "dup_count", "flags", "note"]
def to_row(r):
    opts = (r["options"] + [""] * 6)[:6]
    return [r["qid"], r["source"], r["course"], r["chapter"], r["qtype"], r["question"],
            opts[0], opts[1], opts[2], opts[3], opts[4], opts[5],
            r["answer"], r["answer_raw"], r.get("dup_count", 1),
            ";".join(r["flags"]), r.get("note", "")]

def write_csv(path, records):
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in records:
            w.writerow(to_row(r))

write_csv(os.path.join(OUT, "tiku_master.csv"), kept)

courses = collections.OrderedDict()
for r in kept:
    courses.setdefault(r["course"], []).append(r)
for name, recs in courses.items():
    safe = re.sub(r'[\\/:*?"<>|]', "_", name)[:60]
    write_csv(os.path.join(OUT, "分课程", safe + ".csv"), recs)

json.dump(yangpub, io.open(os.path.join(OUT, "仅答案序列_杨pub.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- 统计报告
st = {
    "原始记录": len(RECS),
    "去重后": len(kept),
    "被去重": len(RECS) - len(kept),
    "跨源答案冲突": dup_conflict,
    "无任何质量标记": sum(1 for r in kept if not r["flags"]),
    "无任何质量标记占比": "%.1f%%" % (100.0 * sum(1 for r in kept if not r["flags"]) / max(1, len(kept))),
    "同时含答案与选项": sum(1 for r in kept if r["answer"] and (r["options"] or r["qtype"] in ("判断", "填空"))),
}
by_src = collections.Counter(r["source"] for r in kept)
by_type = collections.Counter(r["qtype"] for r in kept)
by_flag = collections.Counter(f for r in kept for f in r["flags"] if f != "跨源答案冲突")
n_conf = sum(1 for r in kept if "conflicts" in r)

lines = ["# 题库总库 · 质检报告", ""]
lines += ["- 生成时间：2026-11-15", "- 来源：github_tiku.zip（6 个 GitHub 题库仓库）", ""]
lines += ["## 一、总量", "", "| 项目 | 数值 |", "|---|---|"]
for k, v in st.items():
    lines.append("| %s | %s |" % (k, v))
lines += ["", "## 二、按来源（去重后）", "", "| 来源 | 题量 |", "|---|---|"]
for k, v in by_src.most_common():
    lines.append("| %s | %d |" % (k, v))
lines += ["", "## 三、按题型", "", "| 题型 | 题量 |", "|---|---|"]
for k, v in by_type.most_common():
    lines.append("| %s | %d |" % (k, v))
lines += ["", "## 四、按课程", "", "| 课程 | 题量 | 文件 |", "|---|---|---|"]
for name, recs in sorted(courses.items(), key=lambda x: -len(x[1])):
    safe = re.sub(r'[\\/:*?"<>|]', "_", name)[:60]
    lines.append("| %s | %d | 分课程/%s.csv |" % (name, len(recs), safe))
lines += ["", "## 五、质量标记", "", "| 标记 | 数量 |", "|---|---|"]
for k, v in by_flag.most_common():
    lines.append("| %s | %d |" % (k, v))
if n_conf:
    lines.append("| 跨源答案冲突 | %d |" % n_conf)

lines += ["", "## 六、答案表示法的归一规则", "",
          "| 原格式 | 归一为 | 依据 |",
          "|---|---|---|",
          "| `answer: \"B\"` / `answer: \"AB\"`（字母） | 原字母串 | lolisaikou、li-butter、YuanSeen 选项型 |",
          "| CustedNG `type:0` `answer: 1`（整数下标） | 0 基下标 → 字母 | 抽样核对：`answer:1` 对应 `options[1]` |",
          "| CustedNG `type:1` `answer:[0,1,2,3]` | 0 基下标集合 → 字母串 | 同上 |",
          "| CustedNG `type:3` `answer: 0/1` | 0 → 正确，1 → 错误 | 抽查语义：真命题取 0，假命题取 1 |",
          "| CustedNG `type:3` 但选项多于 2 个 | 改判为单选，下标 → 字母 | 源数据把 type:3 标签混用，按选项数纠正 |",
          "| CustedNG `type:3` 但答案索引 ≥2 且无选项 | 保留题干，答案置空并标记 | 源数据丢了选项，无法还原 |",
          "| YuanSeen `panduan` `answer: A/B` | A → 正确，B → 错误 | 抽查语义一致 |",
          "| CustedNG `type:2` `answer:[文本]` | 文本（多空用 ` / ` 连接） | 填空题无选项 |",
          "| SWERecker `正确答案： AC` + `A、… B、…` | 拆出选项 + 字母串 | 正则按 `[A-H]、` 分切 |",
          "| SoraNoNeko 6 列 CSV（GB18030） | 题干+4 选项+答案字母 | 已转 UTF-8；题干尾部 `易/难` 移入章节字段 |",
          "| SWERecker 无选项、答案为 `√/×` | 改判为判断题 | 题干是陈述句，选项列为空 |",
          "| 标成单选但答案是多个字母 | 改判为多选 | 答案长度即题型证据 |",
          "| 选项中间出现空串 | 保留占位，不删除 | 删掉会让答案字母整体错位 |",
          ""]

lines += ["## 七、已知局限", "",
          "- **判断题映射是推定**：CustedNG 与 YuanSeen 的判断题都没有选项文本，`0/1`→`正确/错误`、`A/B`→`正确/错误` 是靠抽样题干语义确认的，不具备全量校验条件。批量使用时建议先小样本试答验证。",
          "- **去重按「题干归一 + 答案」判定**，同一道题在不同题库被改写过措辞的不会合并；`dup_count` 记录合并了几条。",
          "- **跨源答案冲突**的题目保留首个来源的答案，其余来源答案记在记录的 `conflicts` 字段，可用 `flags=跨源答案冲突` 筛出人工复核。",
          "- **杨pub 两个文件（special/weekly）只有答案序列、没有题干**，无法作为题目入库，单独保存为 `仅答案序列_杨pub.json`（152 + 52 个专题）。",
          "- **CustedNG 的 `-multi.xls` / `-single.xls`** 是其 JSON 的原始导入表，未重复入库。",
          "- **YuanSeen 源文件的 `id` 字段有重复**（tk003~tk009 都写成 `tk005`），若按 `id` 归属会把 6 个不同题库并成「马原 8281 题」；本库改用**文件名**绑定课程（`json_tk005.json` → 马原）。",
          "- 各来源仓库版权归原作者，此处仅作个人学习用途的本地整理。",
          ""]
io.open(os.path.join(OUT, "质检报告.md"), "w", encoding="utf-8").write("\n".join(lines))

# 索引
summary = {
    "生成时间": "2026-11-15",
    "来源压缩包": r"D:\资料库大全\Tabbit浏览器\github_tiku.zip",
    "总题数": len(kept),
    "原始条目": len(RECS),
    "去重条目": len(RECS) - len(kept),
    "按来源": dict(by_src),
    "按题型": dict(by_type),
    "按课程": {k: len(v) for k, v in courses.items()},
}
json.dump(summary, io.open(os.path.join(OUT, "索引.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print("\nTOTAL raw=%d kept=%d dup=%d conflict=%d" % (len(RECS), len(kept), len(RECS) - len(kept), dup_conflict))
print("flags:", dict(by_flag))
print("types:", dict(by_type))
print("courses:", {k: len(v) for k, v in courses.items()})
