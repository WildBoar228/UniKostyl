// Copyright (c) 2025+ Igor Golovachenko <igolovachenko2007@gmail.com>
// This work is licensed under the MIT license, see the file LICENSE for details.

#include <iostream>

extern "C" {
    struct Thresholds_t {
        int Lmin = 0, Lmax = 100, Amin = 0, Amax = 255, Bmin = 0, Bmax = 255;
    };

    struct MyStack_t {
        int* elems;
        int cnt = 0;

        MyStack_t() {
            elems = (int*)calloc(256, sizeof(int));
        }

        ~MyStack_t() {
            free(elems);
        }

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
    };

    // h[L][A][B]: distance to closest 1 in the direction of A increasing
    int h[101][256][256];

    // h2[A][B]: min { h[L][A][B] for L in [L1; L2] }
    int h2[256][256];
    
    // lft[A][B'], rght[A][B']: distance to B-dimension bounds
    // of the largest rect with bottom side A and top bound in column B'
    int lft[256][256], rght[256][256];

    // Finds subthreshold of max size which does not include noise colors
    // 3D extension for the algorithm described there: http://www.e-maxx-ru.1gb.ru/algo/maximum_zero_submatrix
    // Time complexity: O(L*L*A*B / S^3)
    // Space complexity: O(L*A*B)
    //
    // f[L][A][B]: whether this color must be removed
    // thr: source thresholds
    // S: compression strength
    Thresholds_t remove_noise(bool(&f)[101][256][256], Thresholds_t& thr, int S = 1) {
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
                    f[L / S][A / S][B / S] |= f[L][A][B];
                }
            }
        }
        Lmin = Lmin / S;
        Lmax = Lmax / S;
        Amin = Amin / S;
        Amax = Amax / S;
        Bmin = Bmin / S;
        Bmax = Bmax / S;

        int compL = 100 / S + 1;
        int compA = 255 / S + 1;
        int compB = 255 / S + 1;

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
                }
                while (!st.empty()) st.pop();

                for (int A = Amin; A <= Amax; ++A) {
                    for (int B = Bmax; B >= Bmin; --B) {
                        while (!st.empty() && h2[A][st.top()] >= h2[A][B])
                            st.pop();
                        rght[A][B] = (st.empty() ? Bmax + 1 : st.top()) - B;
                        st.push(B);
                    }
                }
                while (!st.empty()) st.pop();

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

        // unzip color space
        answer.Lmin = answer.Lmin * S;
        answer.Lmax = std::min(100, answer.Lmax * S + S - 1);
        answer.Amin = answer.Amin * S;
        answer.Amax = std::min(255, answer.Amax * S + S - 1);
        answer.Bmin = answer.Bmin * S;
        answer.Bmax = std::min(255, answer.Bmax * S + S - 1);

        return answer;
    }

    bool f[101][256][256];

    void test() {
        Thresholds_t thr = { 0, 0, 0, 7, 0, 7 };

        for (int L = 0; L <= 100; ++L) {
            for (int A = 0; A <= 255; ++A) {
                for (int B = 0; B <= 255; ++B) {
                    f[L][A][B] = 0;
                }
            }
        }

        f[0][6][0] = 1;
        f[0][1][1] = 1;
        f[0][0][6] = 1;
        f[0][3][6] = 1;
        f[0][5][7] = 1;

        //auto start = std::chrono::steady_clock::now();

        Thresholds_t new_thr = remove_noise(f, thr, 1);

        //auto finish = std::chrono::steady_clock::now();
        //std::chrono::duration<double> spent = finish - start;

        printf("(%d..%d, %d..%d, %d..%d)", new_thr.Lmin, new_thr.Lmax, new_thr.Amin, new_thr.Amax, new_thr.Bmin, new_thr.Bmax);
        //cout << spent.count() << endl;
    }

    int main() {
        test();
        return 0;
    }
}

