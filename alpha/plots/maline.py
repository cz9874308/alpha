#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Author: Aaron-Yang [code@jieyu.ai]
Contributors: 

"""
import logging
from typing import List, Tuple

import arrow
import numpy as np
from omicron.core.timeframe import tf
from omicron.core.types import FrameType, Frame
from omicron.models.security import Security
from pyemit import emit

from alpha.core import features
from alpha.core.enums import Events
from alpha.monitor.manager import Monitor

logger = logging.getLogger(__name__)


class MALinePlot():
    """
    根据均线支撑（反压）发出买入或者卖出信号

    超频三， 2020-8-14，周线,8/20触达周线，买入后上涨20%
    ------------------------------
    ma5, err=0.007,a=-0.0003,b=0.0269,vx=50.6	slp3:0.06
    ma10, err=0.003,a=0.0006,b=0.0081,vx=-6.4	slp3:0.05
    ma20, err=0.003,a=0.0002,b=-0.0017,vx=5.4	slp3:0.00

    """

    adj_60 = 0.015  # 股价接近60日均线，价差不超过1.5%
    war5 = 0.1      # 5日均线，后5个交易日累计上涨幅度（week advance ratio)，下同
    war10 = 0.05
    war20 = 0.02
    war60 = 0.01

    def __init__(self, scheduler, trade_time_only=True):
        self.name = self.__class__.__name__
        self.monitor = Monitor(scheduler, self, trade_time_only)

    def watch(self, freq=3, **params):
        self.monitor.watch(freq, params)

    async def evaluate(self, code: str, ma_win: List[int], frame_type: FrameType,
                       test_long=True, dt: Frame = None):
        logger.debug("测试%s，参数: %s,%s,%s,%s",
                     code, ma_win, frame_type, test_long, dt)
        if test_long:
            await self.test_long(code, ma_win, frame_type, dt)

    async def test_long(self, code: str, ma_win: List[int], frame_type: FrameType,
                        dt: Frame = None):
        n_bars = max(ma_win) + 20
        stop = dt or arrow.now().datetime
        start = tf.shift(stop, -n_bars, frame_type)
        sec = Security(code)
        bars = await sec.load_bars(start, stop, frame_type)
        if 60 in ma_win:
            await self.test_ma60_long(code, bars)

    async def test_ma60_long(self, code: str, bars: np.array):
        """
        如果股价前期经过大涨，后回调整理，在60日线上获得支撑，为买入信号。

        如果近期股价强势，则会表现为短均线成向上抛物线，最低点在60日线上方，但对60线的方向，
        不做过多要求，向上，或者平盘，或者向下但近期处于转折点即可。（恒泰艾普，2020-7-29）

        如果比较弱势，则会贴着60日线上行，均线粘合。此时短均线再度发散为买点。这种情况要求60
        日均线必须向上。

        Args:
            code:
            bars:

        Returns:

        """
        sec = Security(code)
        end_dt = bars[-1]['frame']
        close = bars['close']
        c0 = close[-1]

        ma_features = features.ma_lines_trend(bars, [5, 10, 20, 60])
        ma5 = ma_features["ma5"][0]
        ma10 = ma_features["ma10"][0]
        ma20 = ma_features["ma20"][0]
        ma60 = ma_features["ma60"][0]

        test_group = np.array([c0, ma5[-1], ma10[-1], ma20[-1]])
        if not np.all(test_group > ma60[-1]):
            logger.debug("%s %s不满足当前价、所有短均线在60线之上的条件", sec, end_dt)
            return

        # 过去7天里曾出现股价接近60日均线
        s60_adj = np.abs(close[:-7] / ma60[:-7] -1)
        if not np.any(s60_adj < self.adj_60):
            logger.debug("%s %s 7日内股价未曾接近60日线", sec, end_dt)
            return

        # 测试短期走势是否符合下杀再拉升特征（黄金坑）
        err, a5, b5, vx5, fit_win = ma_features["ma5"][1]
        t1 = self.is_curve_up(ma_features["ma5"][1], 5)

        err, a10, b10, vx10, fit_win = ma_features["ma10"][1]
        t2 = err < self.Params.fit10_err and self.is_curve_up(a10, vx10, fit_win, 10)

        err, a20, b20, vx20, fit_win = ma_features["ma20"][1]
        t3 = err < self.Params.fit20_err and self.is_curve_up(a20, vx, fit_win, 20)

        if t1 and t2 and t3:
            logger.info("FIRE LONG: %s %s %s 触及60日线，多周期均线向上", sec, end_dt, self.name)
            await emit.emit(Events.sig_long, {
                "plot":    self.name,
                "code":    code,
                "fire_on": end_dt,
                "desc":    f"{sec.display_name}触发60日均线支撑买入策略。",
                "params":  {
                    "s60_adj": s60_adj,
                    "5":       (a5, b5),
                    "10":      (a10, b10),
                    "20":      (a20, b20),
                    "60":      (a60, b60)
                }
            })

        # 要求60日线方向向上
        err, a60, b60, vx, fit_win = ma_features["ma60"][1]
        logger.info("%s, %s, %s, %s, %s, %s",
                    code, err, self.is_curve_up(a60, b60, vx, fit_win, 60)
                    , a60, b60, vx)
        if err > self.Params.fit60_err or \
                not self.is_curve_up(a60, b60, vx, fit_win, 60):
            logger.debug("%s %s 60日均线无法拟合为符合斜率要求的向上直线", sec, end_dt)
            return

    def is_curve_up(self, features: Tuple, ma_win: int):
        err, a5, b5, vx5, fit_win = features



    async def test_short(self, code: str, ma_win: List[int], frame_type: FrameType):
        pass
