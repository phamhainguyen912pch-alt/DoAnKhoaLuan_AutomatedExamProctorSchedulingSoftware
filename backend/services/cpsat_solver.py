"""Mô hình tối ưu xếp lịch gác thi bằng Google OR-Tools CP-SAT.

Module này chỉ nhận dữ liệu đã chuẩn hóa và trả về kết quả; không chứa API
hoặc truy vấn SQL để có thể kiểm thử độc lập.
"""
from __future__ import annotations
from collections import defaultdict
from math import floor
from time import monotonic
from typing import Any

try:
    from ortools.sat.python import cp_model
except ImportError:  # Hiển thị thông báo rõ nếu chưa cài requirements
    cp_model = None


def _range_for(exam: dict[str, Any]) -> tuple[int, int]:
    period = str(exam.get("period", ""))
    import re
    match = re.search(r"(\d+)\s*[→>-]\s*(\d+)", period)
    if match:
        return int(match.group(1)), int(match.group(2))
    session = int(exam.get("ses", 0) or 0)
    return {1: (1, 2), 2: (3, 4), 3: (7, 8), 4: (9, 10)}.get(session, (0, 0))


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a1, a2 = _range_for(a)
    b1, b2 = _range_for(b)
    return a1 < b2 and b1 < a2


def _busy_info(lecturer: dict[str, Any], exam: dict[str, Any]) -> dict[str, Any] | None:
    date = str(exam.get("date", ""))
    start, end = _range_for(exam)
    for item in lecturer.get("busy") or []:
        busy = item if isinstance(item, dict) else {"key": str(item), "priority": 3}
        key = str(busy.get("key", ""))
        if not key.startswith(date + "|"):
            continue
        block = key.split("|", 1)[1]
        bstart, bend = (1, 6) if block == "S" else (7, 12)
        if start <= bend and bstart <= end:
            return busy
    return None


def _teaching_conflict(lecturer: dict[str, Any], exam: dict[str, Any]) -> bool:
    date = str(exam.get("date", ""))
    start, end = _range_for(exam)
    import re
    for raw in lecturer.get("teach") or []:
        parts = str(raw).split("|", 1)
        if len(parts) != 2 or parts[0] != date:
            continue
        match = re.match(r"\s*(\d+)\s*[→>-]\s*(\d+)\s*$", parts[1])
        if match and start < int(match.group(2)) and int(match.group(1)) < end:
            return True
    return False


def _quotas(lecturers: list[dict[str, Any]], exams: list[dict[str, Any]]) -> dict[str, int]:
    total = sum(max(0, int(e.get("need", 0) or 0)) for e in exams)
    active = [l for l in lecturers if float(l.get("pct", 0) or 0) > 0]
    pct_sum = sum(float(l.get("pct", 0) or 0) for l in active)
    result = {str(l.get("id")): 0 for l in lecturers}
    if not pct_sum:
        return result
    fractions = []
    used = 0
    for lec in active:
        exact = total * float(lec.get("pct", 0) or 0) / pct_sum
        base = floor(exact + 1e-9)
        result[str(lec.get("id"))] = base
        used += base
        fractions.append((lec, exact - base))
    fractions.sort(key=lambda pair: (-float(pair[0].get("pct", 0) or 0), -pair[1], str(pair[0].get("id"))))
    i = 0
    while used < total and fractions:
        result[str(fractions[i % len(fractions)][0].get("id"))] += 1
        used += 1
        i += 1
    return result


def solve_schedule(payload: dict[str, Any]) -> dict[str, Any]:
    if cp_model is None:
        raise RuntimeError("Chưa cài Google OR-Tools. Hãy chạy: python -m pip install -r requirements.txt")

    started = monotonic()
    lecturers = list(payload.get("lecturers") or [])
    exams = list(payload.get("exams") or [])
    soft = payload.get("soft") or {}
    if not lecturers or not exams:
        return {"status": "INVALID", "assignments": [], "missing": 0,
                "objective_value": None, "wall_time_seconds": monotonic()-started,
                "message": "Cần có ít nhất một giảng viên và một ca thi."}

    lec_by_id = {str(l.get("id")): l for l in lecturers}
    exam_by_id = {str(e.get("id")): e for e in exams}
    quota = _quotas(lecturers, exams)
    model = cp_model.CpModel()
    x: dict[tuple[str, str], Any] = {}

    for exam in exams:
        eid = str(exam.get("id"))
        for lec in lecturers:
            lid = str(lec.get("id"))
            x[(eid, lid)] = model.NewBoolVar(f"assign_{len(x)}")

    # Mỗi ca phải đủ số giảng viên được yêu cầu.
    for exam in exams:
        eid = str(exam.get("id"))
        need = max(0, int(exam.get("need", 0) or 0))
        model.Add(sum(x[(eid, str(l.get("id")))] for l in lecturers) == need)

    # Mỗi giảng viên nhận đúng định mức, theo tỷ lệ phần trăm.
    for lec in lecturers:
        lid = str(lec.get("id"))
        model.Add(sum(x[(str(e.get("id")), lid)] for e in exams) == quota[lid])

    # Giảng viên không thể nhận các ca thi bị trùng giờ; không xếp trùng lịch dạy.
    for lec in lecturers:
        lid = str(lec.get("id"))
        for i, a in enumerate(exams):
            aid = str(a.get("id"))
            if _teaching_conflict(lec, a):
                model.Add(x[(aid, lid)] == 0)
            busy = _busy_info(lec, a)
            if busy and int(busy.get("priority", 3) or 3) == 1:
                model.Add(x[(aid, lid)] == 0)
            for b in exams[i+1:]:
                if str(a.get("date")) == str(b.get("date")) and _overlap(a, b):
                    model.Add(x[(aid, lid)] + x[(str(b.get("id")), lid)] <= 1)

    # Giữ phân công đã khóa; nếu khóa vi phạm hard constraint, CP-SAT sẽ báo infeasible.
    for exam in exams:
        eid = str(exam.get("id"))
        locked = [str(a.get("l")) for a in (exam.get("asg") or []) if a.get("lock")]
        for lid in locked:
            if lid in lec_by_id:
                model.Add(x[(eid, lid)] == 1)
        for lec in lecturers:
            lid = str(lec.get("id"))
            if lid not in locked:
                model.Add(x[(eid, lid)] == 0) if False else None

    # Không trộn loại hình thi trong cùng buổi của một giảng viên.
    for lec in lecturers:
        lid = str(lec.get("id"))
        buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for exam in exams:
            buckets[(str(exam.get("date")), str(exam.get("half", "")))].append(exam)
        for bucket in buckets.values():
            for i, a in enumerate(bucket):
                for b in bucket[i+1:]:
                    if str(a.get("kind")) != str(b.get("kind")):
                        model.Add(x[(str(a.get("id")), lid)] + x[(str(b.get("id")), lid)] <= 1)

    # Hàm mục tiêu: né lịch bận (soft), ưu tiên lịch gọn trong ngày và tránh lỗ hổng buổi.
    penalties = []
    s2 = soft.get("S2", {}) if isinstance(soft, dict) else {}
    s2_on = bool(s2.get("on", True))
    for exam in exams:
        eid = str(exam.get("id"))
        for lec in lecturers:
            lid = str(lec.get("id"))
            busy = _busy_info(lec, exam)
            if busy and s2_on:
                priority = int(busy.get("priority", 3) or 3)
                weight = 1000 if priority == 1 else (6 if priority == 2 else 2)
                penalties.append(weight * x[(eid, lid)])

    # Nếu một giảng viên được xếp ca ở buổi Sáng và Chiều cùng ngày thì thưởng cho lịch liền mạch.
    # Tạo biến phụ cho việc sử dụng từng nửa ngày, sau đó phạt số block hoạt động.
    gap_weight = int((soft.get("S1", {}) or {}).get("w", 6)) if isinstance(soft, dict) else 6
    if isinstance(soft, dict) and (soft.get("S1", {}) or {}).get("on", True):
        for lec in lecturers:
            lid = str(lec.get("id"))
            by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for exam in exams:
                by_day[str(exam.get("date"))].append(exam)
            for day_exams in by_day.values():
                sessions: dict[str, list[Any]] = defaultdict(list)
                for exam in day_exams:
                    sessions[str(exam.get("ses", ""))].append(x[(str(exam.get("id")), lid)])
                used_vars = []
                for ses, vars_ in sessions.items():
                    used = model.NewBoolVar(f"used_{lid}_{day_exams[0].get('date')}_{ses}")
                    model.AddMaxEquality(used, vars_)
                    used_vars.append((int(ses) if ses.isdigit() else 0, used))
                used_vars.sort(key=lambda z: z[0])
                for i in range(1, len(used_vars)):
                    prev_s, prev = used_vars[i-1]
                    cur_s, cur = used_vars[i]
                    if cur_s - prev_s > 1:
                        gap = model.NewBoolVar(f"gap_{lid}_{day_exams[0].get('date')}_{prev_s}_{cur_s}")
                        model.Add(gap >= prev + cur - 1)
                        penalties.append(gap_weight * 5 * (cur_s-prev_s-1) * gap)

    model.Minimize(sum(penalties) if penalties else 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(payload.get("time_limit_seconds", 20) or 20)
    solver.parameters.num_search_workers = 8
    status_code = solver.Solve(model)
    status = solver.StatusName(status_code)
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": status, "assignments": [], "missing": sum(max(0, int(e.get("need", 0) or 0)) for e in exams),
                "objective_value": None, "wall_time_seconds": solver.WallTime(),
                "message": "Không tìm được lịch thỏa tất cả ràng buộc cứng. Hãy kiểm tra định mức, lịch dạy, lịch bận mức 1 và các phân công đã khóa."}

    assignments = []
    for exam in exams:
        eid = str(exam.get("id"))
        locked_ids = {str(a.get("l")) for a in (exam.get("asg") or []) if a.get("lock")}
        for lec in lecturers:
            lid = str(lec.get("id"))
            if solver.Value(x[(eid, lid)]):
                assignments.append({"exam_id": exam.get("id"), "lecturer_id": lec.get("id"), "locked": lid in locked_ids})
    needed = sum(max(0, int(e.get("need", 0) or 0)) for e in exams)
    missing = max(0, needed - len(assignments))
    return {"status": status, "assignments": assignments, "missing": missing,
            "objective_value": solver.ObjectiveValue(), "wall_time_seconds": solver.WallTime(),
            "message": "Đã tìm được lịch bằng Google OR-Tools CP-SAT."}
