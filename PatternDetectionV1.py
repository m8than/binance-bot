from typing import Pattern
import numpy as np
from scipy.signal import argrelextrema
from enum import Enum
import pandas as pd
import matplotlib.pyplot as plt

class PatternTypes(Enum):
    NONE = 0
    DOUBLE_TOP = 1
    DOUBLE_BOTTOM = 2
    ROUNDING_BOTTOM = 3
    CUP_AND_HANDLE = 4
    RISING_WEDGE = 5
    FALLING_WEDGE = 6
    INVERSE_HEAD_AND_SHOULDERS = 7
    HEAD_AND_SHOULDERS = 8
    ROUNDING_TOP = 9
    ASCENDING_TRIANGLE = 10
    DESCENDING_TRIANGLE = 11

# TODO: detect rounding bottom and top, detect cup and handle

# add pattern strength (how large the differences are)
class PatternDetection:
    @staticmethod
    def detectPattern(klines, smoothing = 2, minimum_distance = 0):
        minmax, distances = PatternDetection.getMinMax(klines, smoothing)
        
        if len(minmax) == 0 or len(distances) == 0:
            return PatternTypes.NONE

        pattern = PatternTypes.NONE
        found_start = 0
        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 5:
                break

            values = minmax[start-4:start+1]
            values_f = [float(i) for i in values]

            peak_distances = distances[start-4:start+1]
            dist_differences = np.diff(peak_distances)

            if all(dist < minimum_distance for dist in dist_differences):
                continue


            if PatternDetection.isRisingWedge(values_f):
                pattern = PatternTypes.RISING_WEDGE
                found_start = start
                break

            if PatternDetection.isFallingWedge(values_f):
                pattern = PatternTypes.FALLING_WEDGE
                found_start = start
                break

            if PatternDetection.isAscendingTriangle(values_f):
                pattern = PatternTypes.ASCENDING_TRIANGLE
                found_start = start
                break

            if PatternDetection.isDescendingTriangle(values_f):
                pattern = PatternTypes.DESCENDING_TRIANGLE
                found_start = start
                break

            if PatternDetection.isDoubleTop(values_f):
                pattern = PatternTypes.DOUBLE_TOP
                found_start = start
                break

            if PatternDetection.isDoubleBottom(values_f):
                pattern = PatternTypes.DOUBLE_BOTTOM
                found_start = start
                break

            if PatternDetection.isInverseHeadAndShoulders(values_f):
                pattern = PatternTypes.INVERSE_HEAD_AND_SHOULDERS
                found_start = start
                break
            
            if PatternDetection.isHeadAndShoulders(values_f):
                pattern = PatternTypes.HEAD_AND_SHOULDERS
                found_start = start
                break


        # get distance of offset from the end of the graph
        distance_from_now = len(klines) - distances[found_start]

        return (pattern, distance_from_now)

    @staticmethod
    def isDoubleTop(values):
        a, b, c, d, e = values
        if a < b and a < c and a < d:
            if b > c and b > e:
                if c > a and c > e:
                    if d > a and d > c and d > e:
                        if abs(b-d) < np.mean([b,d]) * 0.005:
                            if abs(a-b) > np.mean([a,b]) * 0.003:
                                if abs(b-c) > np.mean([b,c]) * 0.001:
                                    return True
        return False

    @staticmethod
    def isDoubleBottom(values):
        a, b, c, d, e = values

        if a > b and a > c and a > d:
            if b < c and b < e:
                if c < a and c < e:
                    if d < a and d > c and d < e:
                        if abs(b-d) < np.mean([b,d]) * 0.05:
                            if abs(a-b) > np.mean([a,b]) * 0.003:
                                if abs(b-c) > np.mean([b,c]) * 0.001:
                                    return True

        return False


    @staticmethod
    def isAscendingTriangle(values):
        a, b, c, d, e = values

        if a > b and b < c and c > d and d < e :
            if abs(a-c) < np.mean([a,c]) * 0.003:
                if abs(c-e) < np.mean([c,e]) * 0.003:
                    if abs(a-e) < np.mean([a,e]) * 0.006:
                        if b < d:
                            return True

        return False

    @staticmethod
    def isDescendingTriangle(values):
        a, b, c, d, e = values

        if a > b and b < c and c > d and d < e:
            if abs(b-d) < np.mean([b,d]) * 0.006:
                    if a > c and c > e:
                        return True

        return False

    @staticmethod
    def isRisingWedge(values):
        a, b, c, d, e = values

        if a > b and b < c and c > d and d < e:
            if c < e:
                if a < c and a < e:
                    if b < d:
                        if abs(a-e) > np.mean([a,e]) * 0.01:
                            return True

        return False

    @staticmethod
    def isFallingWedge(values):
        a, b, c, d, e = values

        if a > b and b < c and c > d and d < e:
            if c > e:
                if a > c and a > e:
                    if b > d:
                        if abs(a-e) > np.mean([a,e]) * 0.01:
                            return True

        return False

    @staticmethod
    def isHeadAndShoulders(values):
        a, b, c, d, e = values
        if c > a and c > b and c > d and c > e:
            if a < b and a < d:
                if e < b and e < d:
                    if abs(b-d) < np.mean([b,d]) * 0.004:
                            return True
        return False

    @staticmethod
    def isInverseHeadAndShoulders(values):
        a, b, c, d, e = values        
        if c < a and c < b and c < d and c < e:
            if a < b and a < d:
                if e < b and e < d:
                    if abs(b-d) < np.mean([b,d]) * 0.004:
                            return True
        return False

    @staticmethod
    def getData(klines):
        graph_data = {}
        for key in klines[0].keys():
            graph_data[key] = []

        for kline in klines:
            for key, value in kline.items():
                graph_data[key].append(value)

        all_data = pd.DataFrame(graph_data)
        all_data = all_data.drop(columns=all_data.columns.difference(['open_price', 'high_price', 'low_price', 'close_price']))
        all_data.dropna(inplace=True)

        return all_data

    @staticmethod
    def getSmoothData(data, smoothing):
        smooth_data = data.rolling(window=smoothing).mean().dropna()
        return smooth_data

    @staticmethod
    def getMinMax(klines, smoothing, column='close_price'):
        data = PatternDetection.getData(klines)
        smooth_prices = PatternDetection.getSmoothData(data, smoothing)

        max_ids = argrelextrema(smooth_prices[column].values, np.greater)[0]
        min_ids = argrelextrema(smooth_prices[column].values, np.less)[0]

        both_ids = list(set(max_ids.tolist() + min_ids.tolist()))
        values = []
        for index in both_ids:
            values.append(smooth_prices[column].values[index])

        # ax = data.reset_index()[column].plot()
        # plt.scatter(both_ids, values, color='orange', alpha=.5)
        # ax.figure.savefig('ye.png')
        
        return (values, both_ids)

    @staticmethod
    def getValues(klines, column):
        return [ kline[column] for kline in klines ]
