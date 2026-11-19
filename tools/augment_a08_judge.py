# -*- coding: utf-8 -*-
"""
将 A08 北高速出入口补齐为「有线索的高风险区域」（服务区深夜聚餐场景）。

背景：A08（北高速出入口，area_type=4）在观察段原本无任何信息库流水、无研判批次、无评分，
      导致前端热力图 / 风险地图上 A08 为空。本脚本为其构造一个贴合高速出入口业务的深夜聚餐场景，
      使其生成高风险线索，前端线索列表与风险地图均能看到 A08。

场景：2026-12-26（周六）凌晨 01:00~02:00，绕城高速北出口服务区出现深夜聚餐——
      多人在服务区餐厅聚餐、在服务区烧烤摊喝酒，随后自行驾车驶出高速。
      该时段命中 F001（≥2 家含酒水场所）+ F002（含酒水消费）+ F004（≥5 辆驶出），
      总分 1.2098 + 2.9667 + 1.9725 = 6.15 → 高风险 → 生成线索 CL2026122606。

数据口径与项目「以案生数、可复算」一致：
  * F001 = 该区域该小时含酒水消费的不同场所数 ≥ 2（需 PL0024 + 新增 PL0031 两家）
  * F002 = 窗口内含酒水消费（has_alcohol=1）
  * F004 = 该区域该小时驶出车辆数 ≥ 5（direction=2）
  其余小时（2/3/4）无酒水、驶出不足 5，评分为 0 → 低风险、无线索，体现「峰谷分明」。

只增不改：除新增 PL0031 一家场所外，不修改任何既有行；编号从 HEAD 续接（VT seq 94、CR seq 31）。

同步更新：sql/risk_alert_示例库.sql 与 frontend/src/api/mock/seed.js（逐行同源）。
"""
import re

SQL = "sql/risk_alert_示例库.sql"
SEED = "frontend/src/api/mock/seed.js"

# ---------------------------------------------------------------- 生成数据
BATCH = "B2026122505"
WINDOW = ("2026-12-25 17:00:00", "2026-12-26 06:00:00")

# 新增场所：服务区烧烤（类型 1 饭店），与 PL0024 服务区餐厅共同构成 F001 的「≥2 家含酒水场所」
NEW_PLACE = ("PL0031", "高速服务区烧烤", 1, "A08", "绕城高速北出口服务区", 1)

# 消费流水（12-26）：hour 1 = 01:xx 聚餐高峰（含酒水 5 笔、2 家场所），hour 2/3/4 无酒水简餐
# (person_id, consume_time, place_id, amount, has_alcohol)
CONSUMES = [
    ("P0010", "2026-12-26 01:10:00", "PL0024", 385.00, 1),
    ("P0011", "2026-12-26 01:15:00", "PL0024", 412.00, 1),
    ("P0012", "2026-12-26 01:20:00", "PL0024", 356.00, 1),
    ("P0013", "2026-12-26 01:25:00", "PL0031", 88.00, 1),
    ("P0014", "2026-12-26 01:30:00", "PL0031", 96.00, 1),
    ("P0015", "2026-12-26 02:40:00", "PL0024", 40.00, 0),
    ("P0016", "2026-12-26 03:10:00", "PL0024", 35.00, 0),
    ("P0017", "2026-12-26 04:05:00", "PL0024", 28.00, 0),
]

# 卡口过车：驶出（direction=2）按小时分布；驶入（direction=1）补真实感
EXITS = {
    1: ["01:05", "01:15", "01:28", "01:40", "01:52"],  # 5 -> F004 命中
    2: ["02:08", "02:20", "02:31"],                     # 3
    3: ["03:10", "03:22"],                               # 2
    4: ["04:05", "04:18"],                               # 2
}
ENTERS = ["01:48", "02:50", "03:40"]

VEHICLES = ["V%04d" % n for n in range(101, 116)]  # V0101..V0115
GATES = ["A08-G01", "A08-G02", "A08-G03"]

# 续接现有编号：HEAD 12-26 过车最大 seq=93、消费最大 seq=30
VT_SEQ0 = 93
CR_SEQ0 = 30

# 4 个区域时段对象：day_type=2（12-26 周六），hour 1~4
# (hour, n_exit, n_consume, score, risk_level, is_clue)
OBJECTS = [
    (1, 5, 5, 6.15, 3, 1),
    (2, 3, 1, 0.00, 1, 0),
    (3, 2, 1, 0.00, 1, 0),
    (4, 2, 1, 0.00, 1, 0),
]

# 各对象特征命中：hit_value 语义（F001=含酒水场所数 / F002=布尔 1/0 / F004=驶出辆数）
FEATURES = {
    1: (1, 1, 1, 2.00, 5.00),
    2: (0, 0, 0, 0.00, 3.00),
    3: (0, 0, 0, 0.00, 2.00),
    4: (0, 0, 0, 0.00, 2.00),
}


def build_tracks():
    """返回 [(record_no, vehicle_id, gate_id, pass_time, direction), ...]"""
    rows = []
    seq = VT_SEQ0
    for hour in (1, 2, 3, 4):
        for t in EXITS[hour]:
            seq += 1
            rows.append(("VT20261226%03d" % seq, VEHICLES[(seq - 1) % len(VEHICLES)],
                         GATES[seq % 3], "2026-12-26 %s:00" % t, 2))
    for t in ENTERS:
        seq += 1
        rows.append(("VT20261226%03d" % seq, VEHICLES[(seq - 1) % len(VEHICLES)],
                     GATES[seq % 3], "2026-12-26 %s:00" % t, 1))
    return rows


def build_consumes():
    """返回 [(record_no, person_id, place_id, consume_time, amount, has_alcohol), ...]"""
    rows = []
    for i, (pid, t, place, amt, alc) in enumerate(CONSUMES, start=CR_SEQ0 + 1):
        rows.append(("CR20261226%03d" % i, pid, place, t, amt, alc))
    return rows


def build_batch():
    return (BATCH, "R001", "V20261001_01", 1, WINDOW[0], WINDOW[1], "A08",
            2, 1, len(OBJECTS), 1, 1523, "U0002", "2026-12-26 08:40:00")


def build_scores():
    """返回 [(score_id, batch_id, rule_id, version_id, object_type, area_id,
               day_type, hour_slot, person_id, sample_size, total_score,
               risk_level, is_clue, created_at), ...]"""
    rows = []
    sid = 179
    for (hour, n_exit, n_consume, score, level, clue) in OBJECTS:
        rows.append((sid, BATCH, "R001", "V20261001_01", 1, "A08", 2, hour,
                     None, n_exit + n_consume, score, level, clue, "2026-12-26 08:40:00"))
        sid += 1
    return rows


def build_features():
    """返回 [(score_id, feature_id, is_hit, weight, hit_value, is_missing), ...]"""
    rows = []
    sid = 179
    for (hour, n_exit, n_consume, score, level, clue) in OBJECTS:
        f1, f2, f4, v_f1, v_f4 = FEATURES[hour]
        rows.append((sid, "F001", f1, 1.2098, v_f1, 0))
        rows.append((sid, "F002", f2, 2.9667, float(f2), 0))
        rows.append((sid, "F004", f4, 1.9725, v_f4, 0))
        sid += 1
    return rows


def build_clue():
    return ("CL2026122606", BATCH, 179, "V20261001_01", 0, "U0002", "2026-12-26 08:41:00")


# ---------------------------------------------------------------- 格式化
def sql_fmt_place(r):
    return "('%s', '%s', %d, '%s', '%s', %d)" % r

def sql_fmt_consume(r):
    return "('%s', '%s', '%s', '%s', %.2f, %d)" % (r[0], r[1], r[2], r[3], r[4], r[5])

def sql_fmt_track(r):
    return "('%s', '%s', '%s', 'A08', '%s', %d)" % (r[0], r[1], r[2], r[3], r[4])

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

# seed.js 字段顺序（各表 .map 解构顺序）
def js_fmt_place(r):
    return "['%s', '%s', %d, '%s']" % (r[0], r[1], r[2], r[3])

def js_fmt_consume(r):
    return "['%s', '%s', '%s', '%s', %.2f, %d]" % (r[0], r[1], r[2], r[3], r[4], r[5])

def js_fmt_track(r):
    return "['%s', '%s', '%s', '%s', %d]" % (r[0], r[1], r[2], r[3], r[4])

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
    """在 INSERT 块结尾（分号前）追加新行。"""
    i = sql.find(table_sig)
    assert i >= 0, "未找到 " + table_sig
    j = sql.find(";", i)
    assert j >= 0
    block = ",\n".join(new_rows)
    return sql[:j] + ",\n" + block + sql[j:]


def js_inject(js, table_name, new_rows):
    """在 seed.js 数组结尾（].map 前）追加新行。"""
    i = js.find(table_name + ": [")
    assert i >= 0, "未找到 " + table_name
    j = js.find("\n    ]", i)
    assert j >= 0
    block = "\n      " + "\n      ".join(new_rows)
    return js[:j] + block + js[j:]


def main():
    place = NEW_PLACE
    consumes = build_consumes()
    tracks = build_tracks()
    batch = build_batch()
    scores = build_scores()
    features = build_features()
    clue = build_clue()

    # ---- SQL ----
    sql = open(SQL, encoding="utf-8").read()
    sql = sql_inject(sql, "INSERT INTO place_info (place_id, place_name, place_type, area_id, address, is_active) VALUES",
                     [sql_fmt_place(place)])
    sql = sql_inject(sql, "INSERT INTO consume_record (record_no, person_id, place_id, consume_time, amount, has_alcohol) VALUES",
                     [sql_fmt_consume(r) for r in consumes])
    sql = sql_inject(sql, "INSERT INTO vehicle_track (record_no, vehicle_id, gate_id, area_id, pass_time, direction) VALUES",
                     [sql_fmt_track(r) for r in tracks])
    sql = sql_inject(sql, "INSERT INTO judge_batch (batch_id, rule_id, version_id, judge_object, data_start, data_end, area_id, run_status, run_no, object_cnt, clue_cnt, duration_ms, operator_id, created_at) VALUES",
                     [sql_fmt_batch(batch)])
    sql = sql_inject(sql, "INSERT INTO risk_score (score_id, batch_id, rule_id, version_id, object_type, area_id, day_type, hour_slot, person_id, sample_size, total_score, risk_level, is_clue, created_at) VALUES",
                     [sql_fmt_score(r) for r in scores])
    sql = sql_inject(sql, "INSERT INTO risk_score_feature (score_id, feature_id, is_hit, weight, hit_value, is_missing) VALUES",
                     [sql_fmt_feature(r) for r in features])
    sql = sql_inject(sql, "INSERT INTO risk_clue (clue_id, batch_id, score_id, version_id, clue_status, assignee_id, create_at) VALUES",
                     [sql_fmt_clue(clue)])

    # ---- seed.js ----
    js = open(SEED, encoding="utf-8").read()
    js = js_inject(js, "place_info", [js_fmt_place(place) + ","])
    js = js_inject(js, "consume_record", [js_fmt_consume(r) + "," for r in consumes])
    js = js_inject(js, "vehicle_track", [js_fmt_track(r) + "," for r in tracks])
    js = js_inject(js, "judge_batch", [js_fmt_batch(batch) + ","])
    js = js_inject(js, "risk_score", [js_fmt_score(r) + "," for r in scores])
    js = js_inject(js, "risk_score_feature", [js_fmt_feature(r) + "," for r in features])
    js = js_inject(js, "risk_clue", [js_fmt_clue(clue) + ","])

    # 全部注入成功后才落盘，避免 SQL 与 seed.js 半一致
    open(SQL, "w", encoding="utf-8").write(sql)
    open(SEED, "w", encoding="utf-8").write(js)

    print("已注入（A08 服务区深夜聚餐 · 高风险）：")
    print("  place_info +1 (%s)" % place[0])
    print("  consume_record +%d" % len(consumes))
    print("  vehicle_track +%d" % len(tracks))
    print("  judge_batch +1 (%s, clue_cnt=1)" % BATCH)
    print("  risk_score +%d" % len(scores))
    print("  risk_score_feature +%d" % len(features))
    print("  risk_clue +1 (%s)" % clue[0])


if __name__ == "__main__":
    main()
