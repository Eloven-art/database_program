# -*- coding: utf-8 -*-
"""
补齐「风险地图 · 区域风险」缺失的研判数据，使 12 个区域在全部 8 个观察夜都有样本点。

背景：前端风险地图按「观察夜(=研判批次 data_start 日期) × 区域」聚合 risk_score(object_type=1)
      的峰值总分。原数据每个观察夜只覆盖 4~5 个区域，其余区域在该夜无评分，
      于是地图上恒定显示「当夜无研判数据」。本脚本为每个缺失的 (观察夜, 区域) 组合
      生成一套完整、业务自洽的研判数据：judge_batch + risk_score + risk_score_feature
      （+ 对中高风险对象生成 risk_clue），使 96 个组合全部覆盖。

业务口径（与项目「以案生数、可复算」一致）：
  * 规则 R001 区域时段：特征 F001(≥2 家含酒水场所, 权重 1.2098) + F002(含酒水消费, 2.9667)
    + F004(自行驾车驶出≥5, 1.9725)；至少命中 2 项才成线索。
  * 总分 = 命中特征权重之和，存储值四舍五入到 2 位小数：
      0.00 / 1.97(F004) / 2.97(F002) / 4.18(F001+F002) / 4.94(F002+F004) / 6.15(全中)
  * 风险等级：>=6 高(3)、>=3 中(2)、其余 低(1)；is_clue = 1 当风险等级>=2（命中>=2 项）。
  * 每个区域有「基准风险等级 + 基准样本量」，叠加一个确定性波动 WAVE，使不同区域
    在不同观察夜自然起伏（高发区域峰值高、低发区域峰值低），无逻辑矛盾、无异常值。

只增不改：不改任何既有行；编号从当前数据续接，天然幂等（重跑会发现 0 个缺失、不注入）。
同步更新：sql/risk_alert_示例库.sql 与 frontend/src/api/mock/seed.js（逐行同源）。
"""
import re
from collections import defaultdict

SQL = "sql/risk_alert_示例库.sql"
SEED = "frontend/src/api/mock/seed.js"

# ---------------------------------------------------------------- 区域画像
AREA_ORDER = ["A01", "A02", "A03", "A04", "A05", "A06",
              "A07", "A08", "A09", "A10", "A11", "A12"]

# 分值阶梯（存储值，2 位小数）
LADDER = [0.00, 1.97, 2.97, 4.18, 4.94, 6.15]

# 基准风险等级（0~5 对应 LADDER 下标）
AREA_BASE_LEVEL = {
    "A01": 5, "A02": 5, "A03": 4, "A04": 4, "A05": 3, "A06": 4,
    "A07": 3, "A08": 2, "A09": 2, "A10": 2, "A11": 4, "A12": 2,
}

# 各等级基准样本量（峰值对象）
LEVEL_SAMPLE = {0: 3, 1: 4, 2: 5, 3: 7, 4: 8, 5: 10}

# 风险波动：按 (night_idx + area_idx) 取偏移，让不同区域在不同夜起伏
WAVE = [0, 1, -1, 2, 0, -2, 1, -1]

# ---------------------------------------------------------------- 观察夜定义
# (obs_date, data_start, data_end, created_date, hours[(day_type, hour) 按峰值→低谷])
NIGHTS = [
    ("2026-11-06", "2026-11-06 00:00:00", "2026-11-09 00:00:00", "2026-11-07",
     [(1, 22), (1, 23), (1, 21), (2, 0)]),
    ("2026-11-13", "2026-11-13 18:00:00", "2026-11-14 03:00:00", "2026-11-14",
     [(1, 20), (1, 21), (1, 19), (2, 1)]),
    ("2026-11-20", "2026-11-20 18:00:00", "2026-11-21 03:00:00", "2026-11-21",
     [(1, 19), (1, 20), (2, 1), (2, 2)]),
    ("2026-11-27", "2026-11-27 18:00:00", "2026-11-28 03:00:00", "2026-11-28",
     [(1, 22), (1, 23), (2, 0), (2, 1)]),
    ("2026-12-04", "2026-12-04 17:00:00", "2026-12-05 06:00:00", "2026-12-05",
     [(1, 18), (1, 17), (2, 0), (2, 3)]),
    ("2026-12-11", "2026-12-11 17:00:00", "2026-12-12 06:00:00", "2026-12-12",
     [(1, 18), (1, 17), (2, 3), (2, 4)]),
    ("2026-12-18", "2026-12-18 17:00:00", "2026-12-19 06:00:00", "2026-12-19",
     [(1, 19), (1, 20), (1, 18), (2, 0)]),
    ("2026-12-25", "2026-12-25 17:00:00", "2026-12-26 06:00:00", "2026-12-26",
     [(2, 1), (2, 2), (2, 3), (2, 4)]),
]

VERSION = "V20261001_01"
RULE = "R001"
OPERATOR = "U0002"
ASSIGNEES = ["U0002", "U0003", "U0008"]

W_F001, W_F002, W_F004 = 1.2098, 2.9667, 1.9725


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def feature_spec(score, jitter):
    """返回 (F001_hit, F002_hit, F004_hit, F001_val, F002_val, F004_val)"""
    j = jitter % 3
    if score == 0.00:
        return (0, 0, 0, 0.0, 0.0, 1.0)
    if score == 1.97:
        return (0, 0, 1, 0.0, 0.0, float(5 + j))
    if score == 2.97:
        return (0, 1, 0, 1.0, 1.0, 1.0)
    if score == 4.18:
        return (1, 1, 0, float(2 + (j % 2)), 1.0, float(3 + (j % 2)))
    if score == 4.94:
        return (0, 1, 1, 1.0, 1.0, float(5 + (j % 2)))
    if score == 6.15:
        return (1, 1, 1, float(3 + j), 1.0, float(5 + j))
    raise ValueError("非法分值 %r" % score)


# ---------------------------------------------------------------- 解析现状
def parse_existing(sql):
    # 全部研判批次（区域 + 个人，个人批次的 area_id 为 NULL）：
    # ('B..', obj_type, data_start, area(或 None), status)
    batches = re.findall(
        r"\('(B\d+)',\s*'R\d+',\s*'V[^']*',\s*(\d),\s*'([^']+)',\s*'[^']+',\s*(?:'([^']*)'|NULL),\s*(\d),",
        sql)
    # 区域时段评分：(score_id, batch_id, area, day_type, hour_slot)
    s = sql.find("INSERT INTO risk_score (score_id, batch_id")
    e = sql.find("INSERT INTO", s + 10)
    rs_block = sql[s:e]
    all_score_ids = [int(x) for x in re.findall(r"\((\d+),\s*'B\d+',", rs_block)]
    region_scores = re.findall(
        r"\((\d+),\s*'(B\d+)',\s*'R\d+',\s*'V[^']*',\s*1,\s*'(A\d{2})',\s*(\d+),\s*(\d+),\s*NULL,",
        rs_block)
    # 线索编号（仅 risk_clue 段）
    c = sql.find("INSERT INTO risk_clue (")
    c2 = sql.find("INSERT INTO", c + 10)
    clue_block = sql[c:c2]
    clue_ids = re.findall(r"'(CL\d+)'", clue_block)
    return {
        "batches": batches,
        "max_score_id": max(all_score_ids) if all_score_ids else 0,
        "region_scores": region_scores,
        "clue_ids": clue_ids,
    }


def build_plan(info):
    # 批次按 id 建索引：batch_id -> data_start
    batch_date = {}
    batch_areas = {}
    for (bid, otype, ds, area, status) in info["batches"]:
        if otype == "1":
            batch_date[bid] = ds[:10]
            batch_areas.setdefault(ds[:10], set()).add(area)

    # 已覆盖 (obs_date, area)
    covered = set()
    for (sid, bid, area, day, hour) in info["region_scores"]:
        d = batch_date.get(bid)
        if d:
            covered.add((d, area))

    # 批次编号续接：按 obs_date 前缀取最大 seq
    obs2prefix = {}
    for (obs, _, _, _, _) in NIGHTS:
        prefix = None
        for (bid, otype, ds, area, status) in info["batches"]:
            if otype == "1" and ds[:10] == obs:
                prefix = bid[:-2]
                break
        obs2prefix[obs] = prefix or ("B" + obs.replace("-", ""))

    # 用前缀统计：对每个 obs，统计其前缀下的最大 seq
    batch_maxseq = defaultdict(int)
    for (obs, _, _, _, _) in NIGHTS:
        p = obs2prefix[obs]
        for (bid, _, _, _, _) in info["batches"]:
            if bid.startswith(p):
                seq = int(bid[-2:])
                batch_maxseq[obs] = max(batch_maxseq[obs], seq)

    # 线索编号续接：按 created_date(obs+1) 的前缀
    clue_date2prefix = {n[3].replace("-", ""): "CL" + n[3].replace("-", "") for n in NIGHTS}
    clue_maxseq = defaultdict(int)
    for cid in info["clue_ids"]:
        for d in clue_date2prefix:
            if cid.startswith("CL" + d):
                clue_maxseq[d] = max(clue_maxseq[d], int(cid[-2:]))

    # 缺失组合
    missing = []
    for ni, (obs, ds, de, cd, hours) in enumerate(NIGHTS):
        for ai, area in enumerate(AREA_ORDER):
            if (obs, area) not in covered:
                missing.append((ni, obs, ds, de, cd, hours, ai, area))

    return {
        "covered": covered,
        "missing": missing,
        "obs2prefix": obs2prefix,
        "batch_maxseq": dict(batch_maxseq),
        "clue_maxseq": dict(clue_maxseq),
        "clue_date2prefix": clue_date2prefix,
    }


# ---------------------------------------------------------------- 生成
def generate(info, plan):
    max_score_id = info["max_score_id"]
    next_score_id = max_score_id + 1

    batches, scores, features, clues = [], [], [], []
    batch_seq = dict(plan["batch_maxseq"])
    clue_seq = dict(plan["clue_maxseq"])

    for (ni, obs, ds, de, cd, hours, ai, area) in plan["missing"]:
        batch_seq[obs] += 1
        batch_id = plan["obs2prefix"][obs] + "%02d" % batch_seq[obs]
        # 批次创建时间：次日清晨，按 (night,area) 错开分钟
        created_at = cd + " 08:%02d:00" % ((ni * 11 + ai * 7) % 60)

        delta = WAVE[(ni + ai) % 8]
        peak_level = clamp(AREA_BASE_LEVEL[area] + delta, 0, 5)
        levels = [peak_level, max(0, peak_level - 1),
                  max(0, peak_level - 2), max(0, peak_level - 3)]

        obj_rows = []  # (score_id, day_type, hour, sample, score, level, is_clue)
        for oi, (day_type, hour) in enumerate(hours):
            lv = levels[oi]
            score = LADDER[lv]
            risk_level = 3 if score >= 6 else (2 if score >= 3 else 1)
            is_clue = 1 if risk_level >= 2 else 0
            seed = ni * 12 + ai * 4 + oi
            sample = max(2, LEVEL_SAMPLE[lv] + (seed % 3) - 1)
            sid = next_score_id
            next_score_id += 1
            obj_rows.append((sid, day_type, hour, sample, score, risk_level, is_clue, seed))
            scores.append((sid, batch_id, RULE, VERSION, 1, area, day_type, hour,
                           None, sample, score, risk_level, is_clue, created_at))
            # 特征行
            f = feature_spec(score, seed + ni)
            features.append((sid, "F001", f[0], W_F001, f[3], 0))
            features.append((sid, "F002", f[1], W_F002, f[4], 0))
            features.append((sid, "F004", f[2], W_F004, f[5], 0))

        clue_cnt = sum(1 for r in obj_rows if r[6] == 1)
        batches.append((batch_id, RULE, VERSION, 1, ds, de, area, 2, 1,
                        4, clue_cnt, 600 + (ni * 137 + ai * 61) % 900,
                        OPERATOR, created_at))

        # 线索：每个中高风险对象一条
        for oi, r in enumerate(obj_rows):
            if r[6] == 1:
                cdate = cd.replace("-", "")
                clue_seq[cdate] += 1
                clue_id = "CL" + cdate + "%02d" % clue_seq[cdate]
                assignee = ASSIGNEES[(ni + ai + oi) % len(ASSIGNEES)]
                clue_at = cd + " 08:%02d:%02d" % (30 + oi, (oi * 13) % 60)
                clues.append((clue_id, batch_id, r[0], VERSION, 0, assignee, clue_at))

    return batches, scores, features, clues


# ---------------------------------------------------------------- 格式化
def sql_fmt_batch(r):
    return "('%s', '%s', '%s', %d, '%s', '%s', '%s', %d, %d, %d, %d, %d, '%s', '%s')" % r


def sql_fmt_score(r):
    person = "NULL" if r[8] is None else "'%s'" % r[8]
    return "(%d, '%s', '%s', '%s', %d, '%s', %d, %d, %s, %d, %.2f, %d, %d, '%s')" % (
        r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], person, r[9], r[10], r[11], r[12], r[13])


def sql_fmt_feature(r):
    return "(%d, '%s', %d, %.4f, %.2f, %d)" % r


def sql_fmt_clue(r):
    return "('%s', '%s', %d, '%s', %d, '%s', '%s')" % r


def js_fmt_batch(r):
    return "['%s', '%s', '%s', %d, '%s', '%s', '%s', %d, %d, %d, %d, %d, '%s', '%s']" % r


def js_fmt_score(r):
    person = "null" if r[8] is None else "'%s'" % r[8]
    return "[%d, '%s', '%s', %d, '%s', %d, %d, %s, %d, %.2f, %d, %d]" % (
        r[0], r[1], r[2], r[4], r[5], r[6], r[7], person, r[9], r[10], r[11], r[12])


def js_fmt_feature(r):
    return "[%d, '%s', %d, %.4f, %.2f, %d]" % r


def js_fmt_clue(r):
    return "['%s', '%s', %d, %d, '%s', '%s', null]" % (r[0], r[1], r[2], r[4], r[5], r[6])


# ---------------------------------------------------------------- 注入
def sql_inject(sql, table_sig, new_rows):
    i = sql.find(table_sig)
    assert i >= 0, "未找到 " + table_sig
    j = sql.find(";", i)
    assert j >= 0
    block = ",\n".join(new_rows)
    return sql[:j] + ",\n" + block + sql[j:]


def js_inject(js, table_name, new_rows):
    i = js.find(table_name + ": [")
    assert i >= 0, "未找到 " + table_name
    j = js.find("\n    ]", i)
    assert j >= 0
    block = "\n      " + "\n      ".join(new_rows)
    return js[:j] + block + js[j:]


def main():
    sql = open(SQL, encoding="utf-8").read()
    info = parse_existing(sql)
    plan = build_plan(info)

    print("已覆盖 (观察夜×区域) 组合数:", len(plan["covered"]))
    print("缺失组合数:", len(plan["missing"]))
    if not plan["missing"]:
        print("无缺失，无需注入（幂等退出）。")
        return

    batches, scores, features, clues = generate(info, plan)

    # 全部生成后统一注入，避免 SQL 与 seed.js 半一致
    sql = sql_inject(sql,
        "INSERT INTO judge_batch (batch_id, rule_id, version_id, judge_object, data_start, data_end, area_id, run_status, run_no, object_cnt, clue_cnt, duration_ms, operator_id, created_at) VALUES",
        [sql_fmt_batch(r) for r in batches])
    sql = sql_inject(sql,
        "INSERT INTO risk_score (score_id, batch_id, rule_id, version_id, object_type, area_id, day_type, hour_slot, person_id, sample_size, total_score, risk_level, is_clue, created_at) VALUES",
        [sql_fmt_score(r) for r in scores])
    sql = sql_inject(sql,
        "INSERT INTO risk_score_feature (score_id, feature_id, is_hit, weight, hit_value, is_missing) VALUES",
        [sql_fmt_feature(r) for r in features])
    sql = sql_inject(sql,
        "INSERT INTO risk_clue (clue_id, batch_id, score_id, version_id, clue_status, assignee_id, create_at) VALUES",
        [sql_fmt_clue(r) for r in clues])

    js = open(SEED, encoding="utf-8").read()
    js = js_inject(js, "judge_batch", [js_fmt_batch(r) + "," for r in batches])
    js = js_inject(js, "risk_score", [js_fmt_score(r) + "," for r in scores])
    js = js_inject(js, "risk_score_feature", [js_fmt_feature(r) + "," for r in features])
    js = js_inject(js, "risk_clue", [js_fmt_clue(r) + "," for r in clues])

    open(SQL, "w", encoding="utf-8").write(sql)
    open(SEED, "w", encoding="utf-8").write(js)

    print("注入完成：")
    print("  judge_batch +%d" % len(batches))
    print("  risk_score +%d" % len(scores))
    print("  risk_score_feature +%d" % len(features))
    print("  risk_clue +%d" % len(clues))
    # 按夜统计新增区域
    from collections import Counter
    per_night = Counter(obs for (ni, obs, *_ ) in plan["missing"])
    for obs in sorted(per_night):
        print("    %s 新增 %d 个区域" % (obs, per_night[obs]))


if __name__ == "__main__":
    main()
