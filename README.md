<p align="center">
  <h1 align="center">🌟 AnyLabeling 🌟</h1>
  <p align="center">Effortless data labeling with AI support<p>
  <p align="center">With <b>Improved Labelme</b> and <b>Segment Anything</b><p>
</p>

![](https://i.imgur.com/waxVImv.png)


## I. Install and run

- Requirements: Python >= 3.8
- Recommended: Miniconda/Anaconda <https://docs.conda.io/en/latest/miniconda.html>

- Create environment:

```
conda create -n anylabeling python=3.8
conda activate anylabeling
```

- **(For macOS only)** Install PyQt5 using Conda:

```
conda install -c conda-forge pyqt==5.15.7
```

- Install anylabeling:

```
pip install anylabeling
```

- Run app:

```
anylabeling
```

Or

```
python -m anylabeling.app
```

## II. Development

- Generate resources:

```
pyrcc5 -o anylabeling/resources/resources.py anylabeling/resources/resources.qrc
```

- Run app:

```
python anylabeling/app.py
```

## III. References

- labelme
- gpu_util
- Icons: Flat Icons
