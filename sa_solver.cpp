#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <random>
#include <algorithm>
#include <chrono>

using namespace std;

// Colors: 0:黑, 1:白, 2:蓝, 3:黄, 4:红, 5:银, 6:棕, 7:灰, 8:金
const int BLK = 0, WHT = 1, BLU = 2, YEL = 3, RED = 4, SLV = 5, BRN = 6, GRY = 7, GLD = 8;

bool ADJ_OK[9][9];

void init_adj() {
    for (int i = 0; i < 9; ++i)
        for (int j = 0; j < 9; ++j)
            ADJ_OK[i][j] = false;

    ADJ_OK[BLK][BLK] = true;
    int blk_nb[] = {WHT, BRN, GRY, SLV};
    for (int c : blk_nb) {
        ADJ_OK[BLK][c] = true;
        ADJ_OK[c][BLK] = true;
    }

    auto allow = [&](int a, int b) {
        ADJ_OK[a][b] = true;
        ADJ_OK[b][a] = true;
    };

    allow(WHT, WHT); allow(WHT, BLU); allow(WHT, BRN);
    allow(YEL, SLV); allow(YEL, GRY); allow(YEL, BRN); allow(YEL, GLD);
    allow(RED, SLV); allow(RED, GRY); allow(RED, BRN); allow(RED, GLD);
    allow(GLD, GRY); allow(GLD, BRN); allow(GLD, SLV);
    allow(GRY, GRY); allow(GRY, SLV);
    allow(SLV, SLV);
    allow(BRN, BRN);
}

struct Car {
    int id; // original index in day
    int day;
    int brand; // 0=A1, 1=A2
    int cfg;   // 0..5
    int diesel;// 0/1
    int fwd;   // 0/1
    int color; // 0..8
};

struct EvalResult {
    long long cost;
    int c_adj;
    int blk_len;
    int blk_gap;
    int fwd_consec;
    int fwd_lt5;
    int fwd_5_9;
    int dsl_consec;
    int dsl_lt5;
    int dsl_5_9;
    int gold_fb;
    int cfg_sw;
    int color_sw;
    int c1_only_in_blk_gap; // count of non-black gaps that have C1-only colors
};

EvalResult evaluate(const vector<vector<Car>>& segs, bool stage2 = false) {
    EvalResult res{};
    int prev_col = -1, prev_cfg = -1, prev_br = -1;
    int blk_run = 0, last_blk_end = -1000;
    int fwd_run = 0, last_fwd_end = -1000;
    int dsl_run = 0, last_dsl_end = -1000;
    bool cur_gap_has_c1_only = false;

    int idx = 0;
    // Flatten-like iteration over 28 segments
    // To check i+1 for gold, we can track prev_col and check gold when we see next
    bool prev_was_gold_needing_yr = false;

    for (int s = 0; s < 28; ++s) {
        const auto& seg = segs[s];
        for (size_t k = 0; k < seg.size(); ++k) {
            const Car& c = seg[k];
            int col = c.color;

            if (prev_was_gold_needing_yr) {
                if (col != YEL && col != RED) {
                    res.gold_fb++;
                }
                prev_was_gold_needing_yr = false;
            }

            if (idx > 0) {
                if (!ADJ_OK[prev_col][col]) res.c_adj++;
                if (c.brand == prev_br && c.cfg != prev_cfg) res.cfg_sw++;
                if (col != prev_col) res.color_sw++;
            }

            if (col == GLD) {
                if (prev_col != YEL && prev_col != RED) {
                    prev_was_gold_needing_yr = true;
                }
            }

            // Black batches
            if (col == BLK) {
                if (blk_run == 0 && last_blk_end >= 0) {
                    int gap = idx - last_blk_end - 1;
                    if (gap < 20) res.blk_gap += (20 - gap);
                    if (cur_gap_has_c1_only) res.c1_only_in_blk_gap++;
                    cur_gap_has_c1_only = false;
                }
                blk_run++;
            } else {
                if (col == BLU || col == YEL || col == RED) {
                    cur_gap_has_c1_only = true;
                }
                if (blk_run > 0) {
                    if (blk_run < 50) res.blk_len += (50 - blk_run);
                    else if (blk_run > 70) res.blk_len += (blk_run - 70);
                    last_blk_end = idx - 1;
                    blk_run = 0;
                }
            }

            // 4WD
            if (c.fwd) {
                if (fwd_run == 0 && last_fwd_end >= 0) {
                    int gap = idx - last_fwd_end - 1;
                    if (gap < 5) res.fwd_lt5 += (5 - gap);
                    else if (gap < 10) res.fwd_5_9 += (10 - gap);
                }
                fwd_run++;
                if (fwd_run > 2) res.fwd_consec++;
            } else {
                if (fwd_run > 0) {
                    last_fwd_end = idx - 1;
                    fwd_run = 0;
                }
            }

            // Diesel
            if (c.diesel) {
                if (dsl_run == 0 && last_dsl_end >= 0) {
                    int gap = idx - last_dsl_end - 1;
                    if (gap < 5) res.dsl_lt5 += (5 - gap);
                    else if (gap < 10) res.dsl_5_9 += (10 - gap);
                }
                dsl_run++;
                if (dsl_run > 2) res.dsl_consec++;
            } else {
                if (dsl_run > 0) {
                    last_dsl_end = idx - 1;
                    dsl_run = 0;
                }
            }

            prev_col = col;
            prev_cfg = c.cfg;
            prev_br = c.brand;
            idx++;
        }
    }
    if (prev_was_gold_needing_yr) res.gold_fb++;
    if (blk_run > 0) {
        if (blk_run < 50) res.blk_len += (50 - blk_run);
        else if (blk_run > 70) res.blk_len += (blk_run - 70);
    }

    if (stage2) {
        long long hard = 0;
        hard += 5000000LL * res.c_adj;
        hard += 5000000LL * res.blk_len;
        hard += 5000000LL * res.blk_gap;
        hard += 100000LL * res.fwd_consec;
        hard += 100000LL * res.fwd_lt5;
        hard += 100000LL * res.dsl_consec;
        hard += 100000LL * res.dsl_lt5;

        long long soft = 0;
        soft += 10000LL * res.fwd_5_9;
        soft += 10000LL * res.dsl_5_9;
        soft += 2000LL * res.gold_fb;
        soft += 200LL * res.c1_only_in_blk_gap;
        soft += 20LL * res.cfg_sw;
        soft += 15LL * res.color_sw;
        res.cost = hard + soft;
    } else {
        long long hard = 0;
        hard += 1000000LL * res.c_adj;
        hard += 1000000LL * res.blk_len;
        hard += 1000000LL * res.blk_gap;
        hard += 1000LL * res.fwd_consec;
        hard += 1000LL * res.fwd_lt5;
        hard += 1000LL * res.dsl_consec;
        hard += 1000LL * res.dsl_lt5;

        long long soft = 0;
        soft += 100LL * res.fwd_5_9;
        soft += 100LL * res.dsl_5_9;
        soft += 100LL * res.gold_fb;
        soft += 10LL * res.c1_only_in_blk_gap;
        soft += 1LL * res.cfg_sw;
        soft += 1LL * res.color_sw;
        res.cost = hard + soft;
    }
    return res;
}

int main(int argc, char** argv) {
    init_adj();
    ifstream fin("cars_input.txt");
    int num_days;
    fin >> num_days;

    vector<vector<Car>> day_cars(num_days);
    for (int d = 0; d < num_days; ++d) {
        int d_idx, n_cars;
        string date_str;
        fin >> d_idx >> date_str >> n_cars;
        day_cars[d].resize(n_cars);
        for (int i = 0; i < n_cars; ++i) {
            Car& c = day_cars[d][i];
            c.id = i;
            c.day = d;
            fin >> c.brand >> c.cfg >> c.diesel >> c.fwd >> c.color;
        }
    }

    // Build initial 28 segments
    vector<vector<Car>> segs(28);
    for (int d = 0; d < num_days; ++d) {
        vector<Car> a1, a2;
        for (const auto& c : day_cars[d]) {
            if (c.brand == 0) a1.push_back(c);
            else a2.push_back(c);
        }
        auto cmp = [](const Car& x, const Car& y) {
            if (x.color != y.color) return x.color < y.color;
            if (x.fwd != y.fwd) return x.fwd < y.fwd;
            if (x.diesel != y.diesel) return x.diesel < y.diesel;
            return x.cfg < y.cfg;
        };
        sort(a1.begin(), a1.end(), cmp);
        sort(a2.begin(), a2.end(), cmp);

        int n_a1_day = (a1.size() + 1) / 2;
        int n_a2_day = a2.size() / 2;

        auto split_bal = [](const vector<Car>& v, int n_first, vector<Car>& f, vector<Car>& s) {
            for (size_t i = 0; i < v.size(); ++i) {
                if ((i % 2 == 0 && (int)f.size() < n_first) || (int)(v.size() - i) <= n_first - (int)f.size()) {
                    f.push_back(v[i]);
                } else {
                    s.push_back(v[i]);
                }
            }
        };

        vector<Car> a1_d, a1_n, a2_d, a2_n;
        split_bal(a1, n_a1_day, a1_d, a1_n);
        split_bal(a2, n_a2_day, a2_d, a2_n);

        auto build_shift = [&](const vector<Car>& sa1, const vector<Car>& sa2, int s_idx) {
            vector<Car> blk1, nb1, blk2, nb2;
            for (const auto& c : sa1) (c.color == BLK ? blk1 : nb1).push_back(c);
            for (const auto& c : sa2) (c.color == BLK ? blk2 : nb2).push_back(c);

            int tot_blk = blk1.size() + blk2.size();
            int b1_len = min((int)blk1.size(), tot_blk / 2);

            // In A1: put {灰,银,黄,红} at start (after A2_nb), and {白,蓝} in middle between blk1 and blk2!
            vector<Car> wht_blu1, oth1;
            for (const auto& c : nb1) {
                if (c.color == WHT || c.color == BLU) wht_blu1.push_back(c);
                else oth1.push_back(c);
            }
            // Interleave 蓝 with 白
            vector<Car> wb_seq;
            vector<Car> w_only, b_only;
            for (const auto& c : wht_blu1) (c.color == WHT ? w_only : b_only).push_back(c);
            size_t wi = 0;
            if (wi < w_only.size()) wb_seq.push_back(w_only[wi++]);
            for (const auto& bc : b_only) {
                wb_seq.push_back(bc);
                if (wi < w_only.size()) wb_seq.push_back(w_only[wi++]);
            }
            while (wi < w_only.size()) wb_seq.push_back(w_only[wi++]);

            // Order oth1: start with 黄/红 (borders 棕 at end of A2_nb), alternate with 灰/银
            vector<Car> yr1, gs1;
            for (const auto& c : oth1) (c.color == YEL || c.color == RED ? yr1 : gs1).push_back(c);
            vector<Car> oth_seq;
            size_t yi = 0, gi = 0;
            while (yi < yr1.size() || gi < gs1.size()) {
                if (yi < yr1.size()) oth_seq.push_back(yr1[yi++]);
                if (gi < gs1.size()) oth_seq.push_back(gs1[gi++]);
                while (yi >= yr1.size() && gi < gs1.size()) oth_seq.push_back(gs1[gi++]);
            }

            vector<Car> s_a1;
            s_a1.insert(s_a1.end(), oth_seq.begin(), oth_seq.end());
            s_a1.insert(s_a1.end(), blk1.begin(), blk1.begin() + b1_len);
            s_a1.insert(s_a1.end(), wb_seq.begin(), wb_seq.end());
            s_a1.insert(s_a1.end(), blk1.begin() + b1_len, blk1.end());

            // In A2: put blk2 first, then nb2 ordered: 白/蓝 -> 棕 -> 黄/红/金/灰/银 -> 棕
            vector<Car> w2, bl2, br2, yr2, gld2, gs2;
            for (const auto& c : nb2) {
                if (c.color == WHT) w2.push_back(c);
                else if (c.color == BLU) bl2.push_back(c);
                else if (c.color == BRN) br2.push_back(c);
                else if (c.color == YEL || c.color == RED) yr2.push_back(c);
                else if (c.color == GLD) gld2.push_back(c);
                else gs2.push_back(c);
            }
            vector<Car> nb2_seq;
            size_t w2i = 0;
            if (w2i < w2.size()) nb2_seq.push_back(w2[w2i++]);
            for (const auto& bc : bl2) {
                nb2_seq.push_back(bc);
                if (w2i < w2.size()) nb2_seq.push_back(w2[w2i++]);
            }
            while (w2i < w2.size()) nb2_seq.push_back(w2[w2i++]);
            // Put all browns after White/Blue, and if >=3 browns, split White around [黄/红/金/灰/银]
            if (br2.size() >= 3 && w2.size() >= 4) {
                size_t first_w_need = max(bl2.size() + 1, w2.size() / 2);
                if (first_w_need < w2.size()) {
                    nb2_seq.clear();
                    size_t wi2 = 0;
                    if (wi2 < first_w_need) nb2_seq.push_back(w2[wi2++]);
                    for (const auto& bc : bl2) {
                        nb2_seq.push_back(bc);
                        if (wi2 < first_w_need) nb2_seq.push_back(w2[wi2++]);
                    }
                    while (wi2 < first_w_need) nb2_seq.push_back(w2[wi2++]);
                    nb2_seq.push_back(br2[0]);
                    size_t y2i = 0, gd2i = 0, gs2i = 0;
                    while (y2i < yr2.size() || gd2i < gld2.size() || gs2i < gs2.size()) {
                        if (y2i < yr2.size()) nb2_seq.push_back(yr2[y2i++]);
                        if (gd2i < gld2.size()) nb2_seq.push_back(gld2[gd2i++]);
                        else if (gs2i < gs2.size()) nb2_seq.push_back(gs2[gs2i++]);
                        if (y2i >= yr2.size() && gd2i >= gld2.size()) {
                            while (gs2i < gs2.size()) nb2_seq.push_back(gs2[gs2i++]);
                        }
                    }
                    nb2_seq.push_back(br2[1]);
                    while (wi2 < w2.size()) nb2_seq.push_back(w2[wi2++]);
                    for (size_t i = 2; i < br2.size(); ++i) nb2_seq.push_back(br2[i]);
                } else {
                    for (size_t i = 0; i < br2.size(); ++i) nb2_seq.push_back(br2[i]);
                    size_t y2i = 0, gd2i = 0, gs2i = 0;
                    while (y2i < yr2.size() || gd2i < gld2.size() || gs2i < gs2.size()) {
                        if (y2i < yr2.size()) nb2_seq.push_back(yr2[y2i++]);
                        if (gd2i < gld2.size()) nb2_seq.push_back(gld2[gd2i++]);
                        else if (gs2i < gs2.size()) nb2_seq.push_back(gs2[gs2i++]);
                        if (y2i >= yr2.size() && gd2i >= gld2.size()) {
                            while (gs2i < gs2.size()) nb2_seq.push_back(gs2[gs2i++]);
                        }
                    }
                }
            } else {
                for (size_t i = 0; i < br2.size(); ++i) nb2_seq.push_back(br2[i]);
                size_t y2i = 0, gd2i = 0, gs2i = 0;
                while (y2i < yr2.size() || gd2i < gld2.size() || gs2i < gs2.size()) {
                    if (y2i < yr2.size()) nb2_seq.push_back(yr2[y2i++]);
                    if (gd2i < gld2.size()) nb2_seq.push_back(gld2[gd2i++]);
                    else if (gs2i < gs2.size()) nb2_seq.push_back(gs2[gs2i++]);
                    if (y2i >= yr2.size() && gd2i >= gld2.size()) {
                        while (gs2i < gs2.size()) nb2_seq.push_back(gs2[gs2i++]);
                    }
                }
            }

            vector<Car> s_a2;
            s_a2.insert(s_a2.end(), blk2.begin(), blk2.end());
            s_a2.insert(s_a2.end(), nb2_seq.begin(), nb2_seq.end());

            segs[2 * s_idx] = s_a1;
            segs[2 * s_idx + 1] = s_a2;
        };

        build_shift(a1_d, a2_d, 2 * d);
        build_shift(a1_n, a2_n, 2 * d + 1);
    }

    mt19937 rng(42);
    double total_sec = (argc > 1) ? stod(argv[1]) : 16.0;
    double stage1_sec = total_sec * 0.5;
    double stage2_sec = total_sec * 0.5;

    auto run_stage = [&](bool stage2, double sec, double temp_start, double temp_end) {
        EvalResult cur = evaluate(segs, stage2);
        EvalResult best = cur;
        auto best_segs = segs;
        auto t0 = chrono::steady_clock::now();
        long long iters = 0;
        while (true) {
            if ((iters & 1023) == 0) {
                double el = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
                if (el >= sec) break;
            }
            double el = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
            double frac = min(1.0, el / sec);
            double temp = temp_start * pow(temp_end / temp_start, frac);
            iters++;

            int mv = rng() % 100;
            if (mv < 45) {
                int k = rng() % 28;
                int n = segs[k].size();
                if (n < 2) continue;
                int i = rng() % n, j = rng() % n;
                if (i == j) continue;
                if (segs[k][i].color != segs[k][j].color) {
                    bool found = false;
                    for (int t = 0; t < 4; ++t) {
                        j = rng() % n;
                        if (i != j && segs[k][i].color == segs[k][j].color) { found = true; break; }
                    }
                    if (!found) continue;
                }
                swap(segs[k][i], segs[k][j]);
                EvalResult nxt = evaluate(segs, stage2);
                long long delta = nxt.cost - cur.cost;
                if (delta <= 0 || uniform_real_distribution<double>(0.0, 1.0)(rng) < exp(-delta / temp)) {
                    cur = nxt;
                    if (cur.cost < best.cost) { best = cur; best_segs = segs; }
                } else {
                    swap(segs[k][i], segs[k][j]);
                }
            } else if (mv < 70) {
                int k = rng() % 28;
                int n = segs[k].size();
                if (n < 2) continue;
                int i = rng() % n, j = rng() % n;
                if (i == j) continue;
                swap(segs[k][i], segs[k][j]);
                EvalResult nxt = evaluate(segs, stage2);
                long long delta = nxt.cost - cur.cost;
                if (delta <= 0 || uniform_real_distribution<double>(0.0, 1.0)(rng) < exp(-delta / temp)) {
                    cur = nxt;
                    if (cur.cost < best.cost) { best = cur; best_segs = segs; }
                } else {
                    swap(segs[k][i], segs[k][j]);
                }
            } else if (mv < 85) {
                int k = rng() % 28;
                int n = segs[k].size();
                if (n < 3) continue;
                int i = rng() % n, j = rng() % n;
                if (i == j) continue;
                Car tmp = segs[k][i];
                segs[k].erase(segs[k].begin() + i);
                segs[k].insert(segs[k].begin() + j, tmp);
                EvalResult nxt = evaluate(segs, stage2);
                long long delta = nxt.cost - cur.cost;
                if (delta <= 0 || uniform_real_distribution<double>(0.0, 1.0)(rng) < exp(-delta / temp)) {
                    cur = nxt;
                    if (cur.cost < best.cost) { best = cur; best_segs = segs; }
                } else {
                    segs[k].erase(segs[k].begin() + j);
                    segs[k].insert(segs[k].begin() + i, tmp);
                }
            } else {
                int d = rng() % 7;
                int b = rng() % 2;
                int k1 = 4 * d + b;
                int k2 = 4 * d + 2 + b;
                int i = rng() % segs[k1].size();
                int j = rng() % segs[k2].size();
                swap(segs[k1][i], segs[k2][j]);
                EvalResult nxt = evaluate(segs, stage2);
                long long delta = nxt.cost - cur.cost;
                if (delta <= 0 || uniform_real_distribution<double>(0.0, 1.0)(rng) < exp(-delta / temp)) {
                    cur = nxt;
                    if (cur.cost < best.cost) { best = cur; best_segs = segs; }
                } else {
                    swap(segs[k1][i], segs[k2][j]);
                }
            }
        }
        segs = best_segs;
        return pair<EvalResult, long long>(best, iters);
    };

    auto greedy_polish = [&](bool stage2) {
        EvalResult best = evaluate(segs, stage2);
        bool improved = true;
        int passes = 0;
        while (improved && passes < 4) {
            improved = false;
            passes++;
            for (int k = 0; k < 28; ++k) {
                int n = segs[k].size();
                for (int i = 0; i < n; ++i) {
                    for (int j = i + 1; j < n; ++j) {
                        if (segs[k][i].color == segs[k][j].color &&
                            segs[k][i].cfg == segs[k][j].cfg &&
                            segs[k][i].fwd == segs[k][j].fwd &&
                            segs[k][i].diesel == segs[k][j].diesel) continue;
                        swap(segs[k][i], segs[k][j]);
                        EvalResult nxt = evaluate(segs, stage2);
                        if (nxt.cost < best.cost) {
                            best = nxt;
                            improved = true;
                        } else {
                            swap(segs[k][i], segs[k][j]);
                        }
                    }
                }
            }
        }
        return best;
    };

    // 1. Pre-polish: fix any initial c_adj / consec violations greedily
    auto b0 = greedy_polish(false);
    cout << "Pre-polish: c_adj=" << b0.c_adj
         << " blk_len=" << b0.blk_len << " blk_gap=" << b0.blk_gap
         << " fwd_c=" << b0.fwd_consec << " fwd_lt5=" << b0.fwd_lt5 << " fwd_59=" << b0.fwd_5_9
         << " dsl_c=" << b0.dsl_consec << " dsl_lt5=" << b0.dsl_lt5 << " dsl_59=" << b0.dsl_5_9
         << " gold_fb=" << b0.gold_fb << "\n";

    // 2. SA with stage2=true (c_adj=5M locked, temp_start=60000 allows fixing 4WD/Diesel=100k!)
    auto [b2, it2] = run_stage(true, total_sec, 60000.0, 0.5);
    cout << "SA (" << it2 << " iters): c_adj=" << b2.c_adj
         << " blk_len=" << b2.blk_len << " blk_gap=" << b2.blk_gap
         << " fwd_c=" << b2.fwd_consec << " fwd_lt5=" << b2.fwd_lt5 << " fwd_59=" << b2.fwd_5_9
         << " dsl_c=" << b2.dsl_consec << " dsl_lt5=" << b2.dsl_lt5 << " dsl_59=" << b2.dsl_5_9
         << " gold_fb=" << b2.gold_fb << "\n";

    // 3. Final greedy polish
    auto best = greedy_polish(true);
    auto best_segs = segs;
    long long iters = it2;

    cout << "Iters: " << iters << " Best cost: " << best.cost << "\n";
    cout << "c_adj=" << best.c_adj
         << " blk_len=" << best.blk_len
         << " blk_gap=" << best.blk_gap
         << " fwd_consec=" << best.fwd_consec
         << " fwd_lt5=" << best.fwd_lt5
         << " fwd_5_9=" << best.fwd_5_9
         << " dsl_consec=" << best.dsl_consec
         << " dsl_lt5=" << best.dsl_lt5
         << " dsl_5_9=" << best.dsl_5_9
         << " gold_fb=" << best.gold_fb
         << " c1_gaps=" << best.c1_only_in_blk_gap
         << " cfg_sw=" << best.cfg_sw
         << " color_sw=" << best.color_sw << "\n";

    ofstream fout("best_order.txt");
    for (int s = 0; s < 28; ++s) {
        for (const auto& c : best_segs[s]) {
            fout << c.day << " " << c.id << " " << c.brand << " " << c.cfg << " "
                 << c.diesel << " " << c.fwd << " " << c.color << "\n";
        }
    }
    return 0;
}
