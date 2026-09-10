"""Safe loading of raw production extracts."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import IO

import pandas as pd

from production_quality.exceptions import DataLoadError

ProductionDataSource = str | PathLike[str] | IO[str] | IO[bytes]


def load_production_data(source: ProductionDataSource) -> pd.DataFrame:
    """Load a production CSV without cleaning or validating business rules.

    Accepts a filesystem path or a file-like object such as ``BytesIO``.
    Raw cell values are preserved so later validation can demonstrate the
    original data-quality problems.
    """

    csv_source: ProductionDataSource | Path
    if isinstance(source, (str, PathLike)):
        path = Path(source)
        if not path.exists():
            raise DataLoadError(f"Production data file does not exist: {path}")
        if not path.is_file():
            raise DataLoadError(
                f"Production data path is not a readable CSV file: {path}"
            )
        csv_source = path
    else:
        csv_source = source

    try:
        frame = pd.read_csv(csv_source, encoding="utf-8")
    except DataLoadError:
        raise
    except pd.errors.EmptyDataError as exc:
        raise DataLoadError("The CSV file contains no columns.") from exc
    except Exception as exc:
        raise DataLoadError(f"The file cannot be read as CSV: {exc}") from exc

    if frame.shape[1] == 0:
        raise DataLoadError("The CSV file contains no columns.")
    if frame.shape[0] == 0:
        raise DataLoadError(
            "The CSV file contains column headers but no production rows."
        )

    return frame.copy()
