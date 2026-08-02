// Copyright (c) 2025+ Igor Golovachenko <igolovachenko2007@gmail.com>
// This work is licensed under the MIT license, see the file LICENSE for details.

#include <algorithm>
#include <cstdlib>

extern "C" {
    struct Thresholds_t {
        int Lmin = 0;
        int Lmax = 100;
        int Amin = 0;
        int Amax = 255;
        int Bmin = 0;
        int Bmax = 255;
    };

    struct MyStack_t {
        int elems[256];
        int cnt = 0;

        void push(int x) {
            elems[cnt++] = x;
        }

        int top() {
            return elems[cnt - 1];
        }

        void pop() {
            --cnt;
        }

        bool empty() {
            return cnt <= 0;
        }

        void clear() {
            cnt = 0;
        }
    };

    // Finds subthreshold of max size which does not include noise colors
    // 3D extension for the algorithm described there: http://www.e-maxx-ru.1gb.ru/algo/maximum_zero_submatrix
    // Time complexity: O(L*L*A*B / S^4)
    // Space complexity: O(L*A*B)
    //
    // f[L][A][B]: whether this color must be removed
    // thr: source thresholds
    // S: compression strength (>= 1)
    Thresholds_t remove_noise(bool f[101][256][256], Thresholds_t thr, int S = 1) {
        bool valid = (
            S > 0 &&
            0 <= thr.Lmin && thr.Lmin <= thr.Lmax && thr.Lmax <= 100 &&
            0 <= thr.Amin && thr.Amin <= thr.Amax && thr.Amax <= 255 &&
            0 <= thr.Bmin && thr.Bmin <= thr.Bmax && thr.Bmax <= 255);
        
        if (!valid) {
            return {0, 0, 0, 0, 0, 0};
        }

        // h[L][A][B]: distance to closest 1 in the direction of A increasing
        thread_local int h[101][256][256];

        // h2[A][B]: min { h[L][A][B] for L in [L1; L2] }
        thread_local int h2[256][256];
        
        // lft[A][B'], rght[A][B']: distance to B-dimension bounds
        // of the largest rect with bottom side A and top bound in column B'
        thread_local int lft[256][256], rght[256][256];

        int Lmin = thr.Lmin;
        int Lmax = thr.Lmax;
        int Amin = thr.Amin;
        int Amax = thr.Amax;
        int Bmin = thr.Bmin;
        int Bmax = thr.Bmax;

        // compress color space
        for (int L = Lmin; L <= Lmax; ++L) {
            for (int A = Amin; A <= Amax; ++A) {
                for (int B = Bmin; B <= Bmax; ++B) {
                    bool val = f[L][A][B];
                    f[L][A][B] = 0;
                    f[L / S][A / S][B / S] |= val;
                }
            }
        }

        Lmin = Lmin / S;
        Lmax = Lmax / S;
        Amin = Amin / S;
        Amax = Amax / S;
        Bmin = Bmin / S;
        Bmax = Bmax / S;

        // auxiliary dp (h)
        for (int L = Lmin; L <= Lmax; ++L) {

            for (int B = Bmin; B <= Bmax; ++B)
                h[L][Amax][B] = (f[L][Amax][B] ? 0 : 1);

            for (int A = Amax - 1; A >= Amin; --A) {
                for (int B = Bmin; B <= Bmax; ++B) {
                    h[L][A][B] = (f[L][A][B] ? 0 : h[L][A + 1][B] + 1);
                }
            }
        }

        int max_size = 0;
        Thresholds_t answer = thr;
        MyStack_t st;

        for (int L1 = Lmin; L1 <= Lmax; ++L1) {

            // first slice
            for (int A = Amin; A <= Amax; ++A) {
                for (int B = Bmin; B <= Bmax; ++B) {
                    h2[A][B] = h[L1][A][B];
                }
            }

            for (int L2 = L1; L2 <= Lmax; ++L2) {
                // add next slice
                for (int A = Amin; A <= Amax; ++A) {
                    for (int B = Bmin; B <= Bmax; ++B) {
                        h2[A][B] = std::min(h2[A][B], h[L2][A][B]);
                    }
                }

                // count left and right bounds (monotonic stack)

                for (int A = Amin; A <= Amax; ++A) {
                    for (int B = Bmin; B <= Bmax; ++B) {
                        while (!st.empty() && h2[A][st.top()] >= h2[A][B])
                            st.pop();
                        lft[A][B] = B - (st.empty() ? Bmin - 1 : st.top());
                        st.push(B);
                    }
                    st.clear();
                }

                for (int A = Amin; A <= Amax; ++A) {
                    for (int B = Bmax; B >= Bmin; --B) {
                        while (!st.empty() && h2[A][st.top()] >= h2[A][B])
                            st.pop();
                        rght[A][B] = (st.empty() ? Bmax + 1 : st.top()) - B;
                        st.push(B);
                    }
                    st.clear();
                }

                // check all rects and update answer
                for (int A = Amin; A <= Amax; ++A) {
                    for (int B = Bmax; B >= Bmin; --B) {

                        int temp_size = (L2 - L1 + 1) * (h2[A][B]) * (rght[A][B] + lft[A][B] - 1);
                        if (temp_size > max_size) {
                            max_size = temp_size;

                            answer.Lmin = L1;
                            answer.Lmax = L2;
                            answer.Amin = A;
                            answer.Amax = A + h2[A][B] - 1;
                            answer.Bmin = B - lft[A][B] + 1;
                            answer.Bmax = B + rght[A][B] - 1;
                        }
                    }
                }
            }
        }

        if (max_size == 0) {
            answer.Lmax = answer.Lmin;
            answer.Amax = answer.Amin;
            answer.Bmax = answer.Bmin;
        }

        // decompress color space
        answer.Lmin = std::max(thr.Lmin, answer.Lmin * S);
        answer.Lmax = std::min(thr.Lmax, answer.Lmax * S + S - 1);
        answer.Amin = std::max(thr.Amin, answer.Amin * S);
        answer.Amax = std::min(thr.Amax, answer.Amax * S + S - 1);
        answer.Bmin = std::max(thr.Bmin, answer.Bmin * S);
        answer.Bmax = std::min(thr.Bmax, answer.Bmax * S + S - 1);

        return answer;
    }
}
