import pandas as pd

import meerkat as mk


def as_data_frame(dp):
    dict_to_ret = {}
    dict_to_ret2 = {}
    for col in dp.columns:
        if isinstance(dp[col], mk.ListColumn) or isinstance(
            dp[col], mk.NumpyArrayColumn
        ):
            dict_to_ret[col] = dp[col].data
        else:
            dict_to_ret2[col] = dp[col].data
    df = pd.DataFrame(dict_to_ret)
    return df, dict_to_ret2


def as_data_panel(df):  # Should be made a constructor
    dp = mk.DataPanel(df.to_dict(orient="list"))
    return dp


def drop_duplicates(
    dp, subset=None, keep="first", inplace=False, ignore_index=False
):  # Keep the index column
    df, na_col = as_data_frame(
        dp
    )  # Splits datapanel into a dataframe made out of normal column
    # types and a dictionary of abnormal column types
    # Add index to subset
    if (
        subset is None or len(subset) == 0
    ):  # If the list of columns to include is empty, make that list every column
        # but 'index' (so all columns are searched for duplicates
        # EXCEPT the index column)

        subset = list(df.columns.copy())
        subset.remove("index")

    # df = df.drop(columns = ['index'])
    df = df.drop_duplicates(subset, keep, inplace, ignore_index)
    # dp = mk.DataPanel.from_pandas(df)
    dp = as_data_panel(df)
    for i in na_col:
        list_index = list(map(int, list(dp["index"])))
        dp[i] = na_col[i][list_index]
    return dp
