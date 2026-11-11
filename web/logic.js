/* Planner calculations for the static site. A line-by-line port of pipeline/insights.py:
 * allocate_moves, redeployment_by_state, jss_places_gap and budget_plan.
 * tests/test_web_logic.py runs this file under Node and checks it against the Python.
 * Works in the browser (window.WT) and in Node (module.exports).
 */
(function (root) {
  "use strict";
  const RANKED = new Set(["A", "B", "C"]);
  const isRanked = (r) => RANKED.has(r.confidence);
  const num = (v) => (v === null || v === undefined || Number.isNaN(v) ? 0 : v);

  /** Within each state, spare teachers move to the neediest ranked LGAs first.
   * Returns a Map pcode -> {moved_in, moved_out, to_hire}. to_hire is null for unranked LGAs. */
  function allocateMoves(lgas, movableShare) {
    const out = new Map();
    for (const r of lgas) out.set(r.adm2_pcode, { moved_in: 0, moved_out: 0, to_hire: null });
    const byState = new Map();
    for (const r of lgas) {
      if (!isRanked(r)) continue;
      if (!byState.has(r.adm1_name)) byState.set(r.adm1_name, []);
      byState.get(r.adm1_name).push(r);
    }
    for (const g of byState.values()) {
      const spareSum = g.reduce((s, r) => s + num(r.teachers_spare), 0);
      const pool = Math.floor(spareSum * movableShare);
      if (pool <= 0) continue;
      let taken = 0;
      const order = g.slice().sort((a, b) => b.need_score - a.need_score);
      for (const r of order) {
        if (taken >= pool) break;
        const take = Math.min(num(r.teachers_needed), pool - taken);
        if (take <= 0) continue; // short of classrooms but not teachers
        out.get(r.adm2_pcode).moved_in = take;
        taken += take;
      }
      const donors = g.filter((r) => num(r.teachers_spare) > 0);
      const donorSum = donors.reduce((s, r) => s + r.teachers_spare, 0);
      for (const r of donors) out.get(r.adm2_pcode).moved_out = (taken * r.teachers_spare) / donorSum;
    }
    for (const r of lgas) {
      if (isRanked(r)) {
        const o = out.get(r.adm2_pcode);
        o.to_hire = num(r.teachers_needed) - o.moved_in;
      }
    }
    return out;
  }

  /** Per state: shortfall, spare, covered by moves, still to hire, share covered. Sorted by shortfall, largest first. */
  function redeploymentByState(lgas, movableShare) {
    const moves = allocateMoves(lgas, movableShare);
    const st = new Map();
    for (const r of lgas) {
      if (!isRanked(r)) continue;
      const m = moves.get(r.adm2_pcode);
      if (!st.has(r.adm1_name)) {
        st.set(r.adm1_name, { adm1_name: r.adm1_name, lgas_ranked: 0, shortfall: 0, spare: 0, covered_by_moves: 0, to_hire: 0 });
      }
      const s = st.get(r.adm1_name);
      s.lgas_ranked += 1;
      s.shortfall += num(r.teachers_needed);
      s.spare += num(r.teachers_spare);
      s.covered_by_moves += m.moved_in;
      s.to_hire += num(m.to_hire);
    }
    const rows = [...st.values()];
    for (const s of rows) s.share_covered = s.shortfall > 0 ? s.covered_by_moves / s.shortfall : null;
    return rows.sort((a, b) => b.shortfall - a.shortfall);
  }

  /** Extra public JSS places for targetTransition of a primary cohort to have a seat; null where not measured. */
  function jssPlacesGap(r, targetTransition) {
    if (r.jss_per_primary_cohort === null || r.jss_per_primary_cohort === undefined) return null;
    const need = (targetTransition * num(r.pry_learners)) / 2 - num(r.jss_learners);
    return Math.ceil(Math.max(need, 0));
  }

  /** Fund rows (already in priority order) until the budget runs out; teachers first within an LGA. */
  function budgetPlan(rows, teacherCost, classroomCost, budget, teachersKey) {
    let left = Number(budget);
    return rows.map((r) => {
      const tNeed = num(r[teachersKey]);
      const cNeed = num(r.classrooms_needed);
      const t = teacherCost > 0 ? Math.min(tNeed, Math.floor(left / teacherCost)) : tNeed;
      left -= t * teacherCost;
      const c = classroomCost > 0 ? Math.min(cNeed, Math.floor(left / classroomCost)) : cNeed;
      left -= c * classroomCost;
      const full = t === tNeed && c === cNeed;
      return {
        adm2_pcode: r.adm2_pcode,
        teachers_funded: t,
        classrooms_funded: c,
        cost_funded: t * teacherCost + c * classroomCost,
        cost_full_gap: tNeed * teacherCost + cNeed * classroomCost,
        status: full ? "Fully funded" : t + c > 0 ? "Partly funded" : "Not reached",
      };
    });
  }

  const api = { allocateMoves, redeploymentByState, jssPlacesGap, budgetPlan, isRanked };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.WT = api;
})(typeof window !== "undefined" ? window : globalThis);
