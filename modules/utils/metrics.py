from functools import lru_cache

import textgrid as tg


class Metric:
    """
    A torchmetrics.Metric-like class with similar methods but lowered computing overhead.
    """

    def update(self, pred, target):
        raise NotImplementedError()

    def compute(self):
        raise NotImplementedError()

    def reset(self):
        raise NotImplementedError()


class VlabelerEditDistance(Metric):
    """
    在vlabeler中，将pred编辑为target所需要的最少次数
    The edit distance between pred and target in vlabeler.
    """

    def __init__(self, move_tolerance=20):
        self.move_tolerance = move_tolerance
        self.errors = 0
        # self.total = 0

    def update(self, pred: tg.PointTier, target: tg.PointTier):
        # 获得从pred编辑到target所需要的最少次数及其比例
        # 注意这是一个略微简化的模型，不一定和vlabeler完全一致。
        # 编辑操作包括：
        #   插入边界
        #   删除边界及其前一个音素（和vlabeler的操作对应）
        #   移动边界（如果边界距离大于move_tolerance ms，就要移动）
        #   音素替换

        # vlabeler中，对TextGrid有要求，如果要满足要求的话，
        # PointTier中的第一个和最后一个边界位置不需要编辑，最后一个音素必定为空
        assert len(pred) >= 2 and len(target) >= 2
        assert pred[0].time == target[0].time
        assert target[-1].time == pred[-1].time
        assert pred[-1].mark == "" and target[-1].mark == ""
        # self.total  = 2 * len(target) - 3

        @lru_cache(maxsize=None)
        def dfs(i, j):
            # 返回将pred[:i]更改为target[:j]所需的编辑次数

            # 边界条件
            if i == 0:
                # 一直插入边界直到j个边界，每次插入一个边界还要修改一个音素，所以是2j
                return j * 2
            if j == 0:
                # 删除边界的同时会删除前方的音素，删除i次
                return i

            # case1: 插入边界，pred[:i+1]只能覆盖到target[:j]，所以要插入一个边界，和target[j+1]对应
            # 如果和上一个音素相同，那么就无需修改音素
            insert = dfs(i, j - 1) + 1
            if j == 1 or target[j - 1].mark != target[j - 2].mark:
                insert += 1
            # case2: 删除边界，pred[:i]已经能覆盖到target[:j+1]，pred[i+1]完全无用，可以删了
            # 这里跟vlabeler的操作是一致的，vlabeler删除一个音素会同时删除前面的边界，这里是删除边界会同时删除后一个音素
            # 因为被删除了，所以无需修改音素
            delete = dfs(i - 1, j) + 1
            # case3:移动（也可以不移动）边界
            # 如果边界距离大于boundary_move_tolerance ms，就要移动，否则不需要
            # 如果音素不一致就要修改，否则不需要
            move = dfs(i - 1, j - 1)
            if abs(pred[i - 1].time - target[j - 1].time) > self.move_tolerance:
                move += 1
            if pred[i - 1].mark != target[j - 1].mark:
                move += 1

            return min(insert, delete, move)

        self.errors = dfs(len(pred), len(target))

    def compute(self):
        return self.errors

    def reset(self):
        self.errors = 0


class VlabelerEditRatio(Metric):
    """
    编辑距离除以target的总长度
    Edit distance divided by total length of target.
    """

    def __init__(self, move_tolerance=20):
        self.edit_distance = VlabelerEditDistance(move_tolerance)
        self.errors = 0
        self.total = 0

    def update(self, pred: tg.PointTier, target: tg.PointTier):
        self.edit_distance.update(pred, target)
        self.errors = self.edit_distance.compute()
        self.total = 2 * len(target) - 3

    def compute(self):
        return self.errors / self.total

    def reset(self):
        self.edit_distance.reset()
        self.errors = 0
        self.total = 0

    # def get_intersection_over_union(
    #     pred: tg.PointTier, target: tg.PointTier, phoneme
    # ):
    #     # 获得pred和target中，phoneme这一音素的交并比
    #     intersection =
