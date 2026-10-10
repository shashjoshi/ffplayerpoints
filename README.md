VERY MUCH WORK IN PROGRESS

Fantasy Football Player Points Prediction Model



Prediction model for players fantasy points in a given weak



Comparison of Linear Regression vs Neural Network, forward tested on ESPN projections(not included in validation testing)



Works for Position players, excludes D/ST and K



Data from 2015/16-2025/26

&#x20;- 2015/2016 only used as backward fill for 2016/17

&#x09;- NGS stats only exists from 2016/17

&#x20;- 2016/17 - 2024/25 used for training

&#x20;- 2025/26 used as out of sample validation data

Data from nflreadpy which pulls from nflverse







Run data --> clean --> features -->



Features creation depends on filter creation's sorting

&#x20;- Ensure that features.createfilters() is ran before features.createfeatures()

