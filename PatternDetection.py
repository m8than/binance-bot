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
    def detectPattern(klines, break_on_first = True):
        pattern = PatternTypes.NONE

        bestPatternDistance = {}

        inverseHeadAndShoulders = PatternDetection.findInverseHeadAndShoulders(klines, break_on_first)
        if len(inverseHeadAndShoulders) > 0:
            bestPatternDistance[PatternTypes.INVERSE_HEAD_AND_SHOULDERS] = inverseHeadAndShoulders[0][0][-1]

        headAndShoulders = PatternDetection.findHeadAndShoulders(klines, break_on_first)
        if len(headAndShoulders) > 0:
            bestPatternDistance[PatternTypes.HEAD_AND_SHOULDERS] = headAndShoulders[0][0][-1]

        descendingTriangles = PatternDetection.findDescendingTriangles(klines, break_on_first)
        if len(descendingTriangles) > 0:
            bestPatternDistance[PatternTypes.DESCENDING_TRIANGLE] = descendingTriangles[0][0][-1]

        ascendingTriangles = PatternDetection.findAscendingTriangles(klines, break_on_first)
        if len(ascendingTriangles) > 0:
            bestPatternDistance[PatternTypes.ASCENDING_TRIANGLE] = ascendingTriangles[0][0][-1]

        doubleBottoms = PatternDetection.findDoubleBottoms(klines, break_on_first)
        if len(doubleBottoms) > 0:
            bestPatternDistance[PatternTypes.DOUBLE_BOTTOM] = doubleBottoms[0][0][-1]

        doubleTops = PatternDetection.findDoubleTops(klines, break_on_first)
        if len(doubleTops) > 0:
            bestPatternDistance[PatternTypes.DOUBLE_TOP] = doubleTops[0][0][-1]

        risingWedges = PatternDetection.findRisingWedges(klines, break_on_first)
        if len(risingWedges) > 0:
            bestPatternDistance[PatternTypes.RISING_WEDGE] = risingWedges[0][0][-1]

        fallingWedges = PatternDetection.findFallingWedges(klines, break_on_first)
        if len(fallingWedges) > 0:
            bestPatternDistance[PatternTypes.FALLING_WEDGE] = fallingWedges[0][0][-1]

        if len(bestPatternDistance) < 1:
            return (PatternTypes.NONE, 0)
        else:
            bestPatternType = max(bestPatternDistance, key=bestPatternDistance.get)
            distance = len(klines) - bestPatternDistance[bestPatternType]
            return (bestPatternType, distance)

    @staticmethod
    def drawGraph(klines, detections, name=''):
        if len(name) < 1:
            name = 'undefined'

        plt.clf()
        ax = PatternDetection.getData(klines).reset_index()['close_price'].plot(color='brown')
        plt.title(name)
        for pattern in detections:
            plt.scatter(pattern[0], pattern[1], color='green', alpha=.7)

        ax.figure.savefig(name + '.png')

    @staticmethod
    def findFallingWedges(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 4)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 6:
                break

            values = minmax[start-5:start+1]
            values_float = [float(i) for i in values]

            a, b, c, d, e, f = values_float

            if a > c > e and b > d > f:
                results.append([distances[start-5:start+1], minmax[start-5:start+1]])
                if break_on_first:
                    break

        return results

    @staticmethod
    def findDoubleBottoms(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 5)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 5:
                break

            values = minmax[start-4:start+1]
            values_float = [float(i) for i in values]

            peak_distances = distances[start-4:start+1]
            dist_differences = np.diff(peak_distances)

            if any(dist < 2 for dist in dist_differences):
                continue

            a, b, c, d, e = values_float

            if a > b < c > d < e:
                if c < a:
                        if abs(b-d) < np.mean([b,d]) * 0.005:
                            results.append([distances[start-4:start+1], minmax[start-4:start+1]])
                            if break_on_first:
                                break

        return results

    @staticmethod
    def findDoubleTops(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 5)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 5:
                break

            values = minmax[start-4:start+1]
            values_float = [float(i) for i in values]

            peak_distances = distances[start-4:start+1]
            dist_differences = np.diff(peak_distances)

            if any(dist < 2 for dist in dist_differences):
                continue

            a, b, c, d, e = values_float

            if a < b > c < d > e:
                if c > a:
                        if abs(b-d) < np.mean([b,d]) * 0.005:
                            results.append([distances[start-4:start+1], minmax[start-4:start+1]])
                            if break_on_first:
                                break

        return results

    @staticmethod
    def findRisingWedges(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 3)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 6:
                break

            values = minmax[start-5:start+1]
            values_float = [float(i) for i in values]

            a, b, c, d, e, f = values_float

            if a < c < e and b < d < f:
                results.append([distances[start-5:start+1], minmax[start-5:start+1]])
                if break_on_first:
                    break

        return results

    @staticmethod
    def findAscendingTriangles(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 5)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 6:
                break

            values = minmax[start-5:start+1]
            values_float = [float(i) for i in values]

            peak_distances = distances[start-5:start+1]
            dist_differences = np.diff(peak_distances)

            if any(dist < 2 for dist in dist_differences):
                continue

            a, b, c, d, e, f = values_float
            
            if a > b < c > d < e > f:
                if b < d < f:
                    if abs(a-c) < np.mean([a,c]) * 0.01:
                        if abs(c-e) < np.mean([c,e]) * 0.01:
                            if abs(a-e) < np.mean([a,e]) * 0.01:
                                results.append([distances[start-5:start+1], minmax[start-5:start+1]])
                                if break_on_first:
                                    break

        return results

    @staticmethod
    def findDescendingTriangles(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 5)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 6:
                break

            values = minmax[start-5:start+1]
            values_float = [float(i) for i in values]

            peak_distances = distances[start-5:start+1]
            dist_differences = np.diff(peak_distances)

            if any(dist < 2 for dist in dist_differences):
                continue

            a, b, c, d, e, f = values_float

            if a < b > c < d > e < f:
                if b > d > f:
                    if abs(a-c) < np.mean([a,c]) * 0.01:
                        if abs(c-e) < np.mean([c,e]) * 0.01:
                            if abs(a-e) < np.mean([a,e]) * 0.01:
                                results.append([distances[start-5:start+1], minmax[start-5:start+1]])
                                if break_on_first:
                                    break

        return results

        
    @staticmethod
    def findHeadAndShoulders(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 4)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 5:
                break

            values = minmax[start-4:start+1]
            values_float = [float(i) for i in values]

            peak_distances = distances[start-4:start+1]
            dist_differences = np.diff(peak_distances)

            if any(dist < 2 for dist in dist_differences):
                continue

            a, b, c, d, e = values_float

            if a > b < c > d < e:
                if c > b and c > d and c > a and c > e:
                    if abs(b-d) < np.mean([b, d]) * 0.005:
                        results.append([distances[start-4:start+1], minmax[start-4:start+1]])
                        if break_on_first:
                            break

        return results

    @staticmethod
    def findInverseHeadAndShoulders(klines, break_on_first):
        minmax, distances = PatternDetection.getMinMax(klines, 4)
        if len(minmax) == 0 or len(distances) == 0:
            return []

        results = []

        for offset in range(len(minmax)):
            start = len(minmax) - 1 - offset

            if start < 5:
                break

            values = minmax[start-4:start+1]
            values_float = [float(i) for i in values]

            peak_distances = distances[start-4:start+1]
            dist_differences = np.diff(peak_distances)

            if any(dist < 2 for dist in dist_differences):
                continue

            a, b, c, d, e = values_float

            if a < b > c < d > e:
                if c < b and c < d and c < a and c < e:
                    if abs(b-d) < np.mean([b, d]) * 0.005:
                        results.append([distances[start-4:start+1], minmax[start-4:start+1]])
                        if break_on_first:
                            break

        return results

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
