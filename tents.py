#!/usr/bin/env python3
"""tents - 帐篷与树 (Tents and Trees) 谜题生成器与求解器。

规则:
- 每棵树(T)必须恰好有一顶帐篷(^)在其上下左右相邻格。
- 每顶帐篷必须恰好与一棵树上下左右相邻(属于这棵树)。
- 帐篷之间不能相邻,包括对角相邻。
- 每行/每列的数字表示该行/该列的帐篷数量。
- 帐篷总数 = 树总数。

纯标准库: argparse / sys / random。Python 3.10+。
"""

import argparse
import random
import sys

DIRS4 = ((-1, 0), (1, 0), (0, -1), (0, 1))

VERSION = "1.0.0"


class _BudgetExceeded(Exception):
    pass


class Puzzle:
    """一则谜题: 棋盘尺寸、树的位置集合、行/列帐篷数。"""

    def __init__(self, size, trees, row_counts, col_counts):
        self.size = size
        self.trees = frozenset(trees)
        self.row_counts = tuple(row_counts)
        self.col_counts = tuple(col_counts)

    def __repr__(self):
        return (f"Puzzle(size={self.size}, trees={len(self.trees)}, "
                f"rows={list(self.row_counts)}, cols={list(self.col_counts)})")


def generate(size=6, n_trees=None, seed=None):
    """随机生成一则有解的谜题,返回 (puzzle, 参考解tents集合)。

    构造法: 先随机放互不接触的帐篷,再为每顶帐篷挑一棵相邻的树
    (保证树不与其他帐篷正交相邻),最后由帐篷反推行列计数。
    这样构造出的帐篷布局天然是谜题的一个合法解。
    """
    rng = random.Random(seed)
    n = size
    n_trees = n_trees if n_trees is not None else n
    if not (1 <= n_trees <= n * n // 3):
        raise ValueError(f"树数不合理: {n_trees}")
    for _attempt in range(1000):
        # 1) 放帐篷: 任意两顶帐篷的 8 邻域不重叠
        cells = [(r, c) for r in range(n) for c in range(n)]
        rng.shuffle(cells)
        tents = []
        blocked = set()
        for cell in cells:
            if cell in blocked:
                continue
            tents.append(cell)
            r, c = cell
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    blocked.add((r + dr, c + dc))
            if len(tents) == n_trees:
                break
        if len(tents) < n_trees:
            continue
        # 2) 为每顶帐篷配一棵树: 树在其正交邻格,且不与其他帐篷正交相邻
        tent_set = set(tents)
        trees = []
        used = set(tents)
        order = list(tents)
        rng.shuffle(order)
        ok = True
        for (r, c) in order:
            cands = []
            for dr, dc in DIRS4:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < n and 0 <= nc < n):
                    continue
                if (nr, nc) in used:
                    continue
                clash = False
                for dr2, dc2 in DIRS4:
                    nb = (nr + dr2, nc + dc2)
                    if nb != (r, c) and nb in tent_set:
                        clash = True
                        break
                if clash:
                    continue
                cands.append((nr, nc))
            if not cands:
                ok = False
                break
            t = rng.choice(cands)
            trees.append(t)
            used.add(t)
        if not ok:
            continue
        row_counts = [0] * n
        col_counts = [0] * n
        for (r, c) in tents:
            row_counts[r] += 1
            col_counts[c] += 1
        return Puzzle(n, trees, row_counts, col_counts), set(tents)
    raise RuntimeError("生成失败次数过多,请换个种子或调小树数重试")


def solve(puzzle, max_nodes=2_000_000):
    """回溯求解,返回帐篷坐标集合; 无解/超预算返回 None。

    每棵树从其正交邻格中选一顶帐篷,候选格预先过滤掉
    "与多棵树相邻"的格子(帐篷必须恰好属于一棵树)。
    """
    n = puzzle.size
    trees = list(puzzle.trees)
    tree_set = puzzle.trees
    if sum(puzzle.row_counts) != len(trees) or sum(puzzle.col_counts) != len(trees):
        return None
    cands = {}
    for (r, c) in trees:
        opts = []
        for dr, dc in DIRS4:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < n and 0 <= nc < n):
                continue
            if (nr, nc) in tree_set:
                continue
            adj = sum(1 for dr2, dc2 in DIRS4
                      if (nr + dr2, nc + dc2) in tree_set)
            if adj != 1:  # 帐篷必须恰好与一棵树正交相邻
                continue
            opts.append((nr, nc))
        if not opts:
            return None
        cands[(r, c)] = opts
    order = sorted(trees, key=lambda t: len(cands[t]))  # MRV
    row_rem = list(puzzle.row_counts)
    col_rem = list(puzzle.col_counts)
    tents = set()
    nodes = [0]

    def touches(r, c):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if (r + dr, c + dc) in tents:
                    return True
        return False

    def rec(i):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            raise _BudgetExceeded
        if i == len(order):
            return all(x == 0 for x in row_rem) and all(x == 0 for x in col_rem)
        for (r, c) in cands[order[i]]:
            if row_rem[r] <= 0 or col_rem[c] <= 0:
                continue
            if touches(r, c):
                continue
            tents.add((r, c))
            row_rem[r] -= 1
            col_rem[c] -= 1
            if rec(i + 1):
                return True
            row_rem[r] += 1
            col_rem[c] += 1
            tents.remove((r, c))
        return False

    try:
        ok = rec(0)
    except _BudgetExceeded:
        return None
    return set(tents) if ok else None


def check_solution(puzzle, tents):
    """校验帐篷布局是否满足全部规则,返回 (ok, 说明)。"""
    n = puzzle.size
    tents = set(tents)
    if len(tents) != len(puzzle.trees):
        return False, f"帐篷数 {len(tents)} != 树数 {len(puzzle.trees)}"
    if tents & puzzle.trees:
        return False, "帐篷不能放在树所在的格子"
    for (r, c) in sorted(puzzle.trees):
        adj = sum(1 for dr, dc in DIRS4 if (r + dr, c + dc) in tents)
        if adj != 1:
            return False, f"树 ({r},{c}) 相邻帐篷数 = {adj},应为 1"
    for (r, c) in sorted(tents):
        adj = sum(1 for dr, dc in DIRS4 if (r + dr, c + dc) in puzzle.trees)
        if adj != 1:
            return False, f"帐篷 ({r},{c}) 相邻树数 = {adj},应为 1"
    for (r, c) in sorted(tents):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if (dr, dc) != (0, 0) and (r + dr, c + dc) in tents:
                    return False, f"帐篷 ({r},{c}) 与另一顶帐篷相邻(含对角)"
    rc = [0] * n
    cc = [0] * n
    for (r, c) in tents:
        if not (0 <= r < n and 0 <= c < n):
            return False, f"帐篷 ({r},{c}) 越界"
        rc[r] += 1
        cc[c] += 1
    if rc != list(puzzle.row_counts):
        return False, f"行计数不符: {rc} vs {list(puzzle.row_counts)}"
    if cc != list(puzzle.col_counts):
        return False, f"列计数不符: {cc} vs {list(puzzle.col_counts)}"
    return True, "合法"


def render(puzzle, tents=None):
    """ASCII 渲染谜题(树=T,帐篷=^,空=.)及行列计数。"""
    n = puzzle.size
    tents = set(tents or ())
    lines = ["    " + " ".join(str(c) for c in range(n)),
             "   +" + "--" * n + "+"]
    for r in range(n):
        row = []
        for c in range(n):
            if (r, c) in tents:
                row.append("^")
            elif (r, c) in puzzle.trees:
                row.append("T")
            else:
                row.append(".")
        lines.append(f"{puzzle.row_counts[r]:>2} |" + " ".join(row) + " |")
    lines.append("   +" + "--" * n + "+")
    lines.append("    " + " ".join(str(x) for x in puzzle.col_counts))
    return "\n".join(lines)


def dump_text(puzzle):
    """谜题文本格式,用于 --save。"""
    n = puzzle.size
    lines = ["tents-puzzle v1", f"size {n}",
             "rows " + " ".join(map(str, puzzle.row_counts)),
             "cols " + " ".join(map(str, puzzle.col_counts))]
    for r in range(n):
        lines.append("".join("T" if (r, c) in puzzle.trees else "."
                             for c in range(n)))
    return "\n".join(lines) + "\n"


def parse_text(text):
    """解析 dump_text 格式,非法抛 ValueError。"""
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if len(lines) < 4 or lines[0] != "tents-puzzle v1":
        raise ValueError("不是 tents 谜题文本")
    try:
        size = int(lines[1].split()[1])
        row_counts = [int(x) for x in lines[2].split()[1:]]
        col_counts = [int(x) for x in lines[3].split()[1:]]
    except (IndexError, ValueError):
        raise ValueError("头部格式错误")
    grid = lines[4:4 + size]
    if len(grid) != size or any(len(ln) != size for ln in grid):
        raise ValueError("棋盘行数/列数与 size 不符")
    trees = set()
    for r, ln in enumerate(grid):
        for c, ch in enumerate(ln):
            if ch == "T":
                trees.add((r, c))
            elif ch != ".":
                raise ValueError(f"第 {r + 1} 行第 {c + 1} 列非法字符: {ch!r}")
    if len(row_counts) != size or len(col_counts) != size:
        raise ValueError("行列计数个数与 size 不符")
    return Puzzle(size, trees, row_counts, col_counts)


def _selftest():
    """内置自检,返回 (通过数, 失败数)。"""
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [通过] {name}")
        else:
            failed += 1
            print(f"  [失败] {name}")

    # 1) 手工 4x4 谜题(答案已手工验算,唯一解 {(1,1),(3,3)})
    p = Puzzle(4, {(0, 1), (2, 3)}, [0, 1, 0, 1], [0, 1, 0, 1])
    sol = solve(p)
    check("手工 4x4 求出唯一解", sol == {(1, 1), (3, 3)})
    check("手工 4x4 解合法", check_solution(p, sol)[0] if sol else False)

    # 2) 矛盾谜题应返回无解
    p2 = Puzzle(2, {(0, 0)}, [1, 0], [1, 0])
    check("矛盾谜题返回无解", solve(p2) is None)

    # 3) 20 个种子: 生成 -> 求解 -> 校验全部规则
    allok = True
    for seed in range(20):
        puz, _ref = generate(6, seed=seed)
        s = solve(puz)
        ok, _msg = check_solution(puz, s) if s is not None else (False, "无解")
        if not ok:
            allok = False
            print(f"    seed={seed} 失败: {_msg}")
            break
    check("20 种子生成谜题全部可解且合法", allok)

    # 4) 文本格式往返
    puz, _ = generate(6, seed=7)
    check("文本格式存取往返一致",
          parse_text(dump_text(puz)).trees == puz.trees
          and parse_text(dump_text(puz)).row_counts == puz.row_counts)

    print(f"自检结果: {passed} 通过, {failed} 失败")
    return passed, failed


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="tents",
        description="帐篷与树(Tents and Trees)谜题生成器与求解器")
    ap.add_argument("--size", type=int, default=6, help="棋盘边长(默认 6,建议 4-8)")
    ap.add_argument("--trees", type=int, default=None, help="树(帐篷)数量,默认等于边长")
    ap.add_argument("--seed", type=int, default=None, help="随机种子,可复现")
    ap.add_argument("--solve", action="store_true", help="对生成的谜题求解并显示答案")
    ap.add_argument("--save", metavar="FILE", help="把生成的谜题存为文本文件")
    ap.add_argument("--load", metavar="FILE", help="从文本文件读入谜题(与 --solve 合用求解)")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检")
    args = ap.parse_args(argv)

    if args.selftest:
        passed, failed = _selftest()
        return 0 if failed == 0 else 1

    if args.load:
        try:
            with open(args.load, encoding="utf-8") as f:
                puzzle = parse_text(f.read())
        except (OSError, ValueError) as e:
            print(f"读入失败: {e}", file=sys.stderr)
            return 2
    else:
        if not (4 <= args.size <= 10):
            print("--size 建议在 4 到 10 之间", file=sys.stderr)
            return 2
        try:
            puzzle, _ref = generate(args.size, n_trees=args.trees, seed=args.seed)
        except (ValueError, RuntimeError) as e:
            print(f"生成失败: {e}", file=sys.stderr)
            return 2
        if args.save:
            try:
                with open(args.save, "w", encoding="utf-8") as f:
                    f.write(dump_text(puzzle))
            except OSError as e:
                print(f"保存失败: {e}", file=sys.stderr)
                return 2

    print(f"帐篷与树 {puzzle.size}x{puzzle.size}(树 {len(puzzle.trees)} 棵):\n")
    print(render(puzzle))

    if args.solve:
        sol = solve(puzzle)
        if sol is None:
            print("\n无解(或搜索超出预算)。")
            return 1
        ok, msg = check_solution(puzzle, sol)
        print(f"\n求解成功,共 {len(sol)} 顶帐篷,校验: {msg}\n")
        print(render(puzzle, sol))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
