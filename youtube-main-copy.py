# 必要なモジュールをimport
import datetime as dt
import math
import os

import gspread
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def main():
    # 環境変数の取得
    load_dotenv(dotenv_path=".env")
    spreadsheet_key = os.getenv("SPREADSHEET_KEY")
    api_key = os.getenv("API_KEY")
    # 2つのAPIを記述しないとリフレッシュトークンを3600秒毎に発行し続けなければならない
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    # 認証情報設定
    # ダウンロードしたjsonファイル名をクレデンシャル変数に設定
    json_file = os.getenv("SERVICE_ACCOUNT_JSON")
    credentials = Credentials.from_service_account_file(json_file, scopes=scope)
    # OAuth2の資格情報を使用してGoogle APIにログインします。
    gc = gspread.authorize(credentials)

    # 共有設定したスプレッドシートの検索キーワードシートを開く
    worksheet = gc.open_by_key(spreadsheet_key).worksheet("検索キーワード")
    keyword_list = worksheet.col_values(1)

    # 今から24時間前の時刻をfromtimeとする（今の時刻のタイムゾーンはYoutubeに合わせて協定世界時刻のutcにする)
    fromtime = dt.datetime.utcnow() - dt.timedelta(hours=24)
    fromtime = fromtime.strftime("%Y-%m-%dT%H:%M:%SZ")
    # データを入れる空のリストを作成
    data = []
    # キーワードリストを元に検索
    for keyword in keyword_list:
        next_page_token = ""
        youtube = build("youtube", "v3", developerKey=api_key)
        # while文でnextPageTokenがあるまで動画データを取得
        while True:
            # youtube.search().listで動画情報を取得。結果は辞書型
            result = (
                youtube.search()
                .list(
                    part="snippet",  # 必須パラメーターのpart
                    q=keyword,  # 検索したい文字列を指定
                    maxResults=50,  # 1回の試行における最大の取得数
                    order="viewCount",  # 視聴回数が多い順に取得
                    publishedAfter=fromtime,  # いつから情報を検索するか？
                    type="video",  # 動画タイプ
                    regionCode="JP",  # 地域コード
                    pageToken=next_page_token,  # ページ送りのトークンの設定
                )
                .execute()
            )

            # 動画数が50件より多い場合はページ送りのトークン(result['nextPageToken']を変数nextpagetokenに設定する
            for item in result["items"]:
                videoId = item["id"]["videoId"]
                publishedAt = item["snippet"]["publishedAt"]
                title = item["snippet"]["title"]
                data.append([videoId, publishedAt, title, keyword])
            next_page_token = result.get("nextPageToken")
            if not next_page_token:
                break

    # videoidリストを作成
    videoid_list = []
    for item in data:
        videoid_list.append(item[0])
    # videoidリストの中の重複を取り除く
    videoid_list = sorted(set(videoid_list), key=videoid_list.index)
    # 50のセットの数(次のデータ取得で最大50ずつしかデータが取れないため、50のセットの数を数えている)
    # math.ceilは小数点以下は繰り上げの割り算　例　math.ceil(3.4) = 4
    data_length = len(data)
    _set_50 = math.ceil(data_length / 50)

    _id_list = []
    for i in range(_set_50):
        _id_list.append(",".join(videoid_list[i * 50 : (i + 1) * 50]))
    # 再生回数データを取得して、再生回数リストを作成
    viewcount_list = []
    for videoid in _id_list:
        viewcount = (
            youtube.videos()
            .list(part="statistics", maxResults=50, id=videoid)
            .execute()
        )
        for item in viewcount["items"]:
            id = item["id"]
            viewcount = item["statistics"]["viewCount"]
            viewcount_list.append([id, viewcount])

    # 動画情報を入れたデータフレームdf_dataの作成
    df_data = pd.DataFrame(data, columns=["videoId", "publishtime", "title", "keyword"])
    # 重複の削除 subsetで重複を判定する列を指定,inplace=Trueでデータフレームを新しくするかを指定,
    df_data.drop_duplicates(subset=["videoId"], inplace=True)
    # 動画のURL
    df_data["url"] = "https://www.youtube.com/watch?v=" + df_data["videoId"]
    # 調査した日
    df_data["search_date"] = dt.date.today().strftime("%Y-%m-%d")
    # 再生回数データを入れたデータフレームdf_viewcountの作成
    df_viewcount = pd.DataFrame(viewcount_list, columns=["videoId", "viewcount"])
    # 2つのデータフレームのマージ
    df_data = pd.merge(df_viewcount, df_data, on="videoId", how="left")
    # viewcountの列のデータを条件検索のためにint型にする(元データも変更)
    df_data["viewcount"] = df_data["viewcount"].astype(int)
    # データフレームのviewcountに記載されている、再生回数が条件を満たす行だけを抽出
    df_data = df_data.query("viewcount >= 100000")
    df_data = df_data[["search_date", "keyword", "title", "url", "viewcount"]]
    # 共有設定したスプレッドシートの検索結果シートを開く
    worksheet = gc.open_by_key(spreadsheet_key).worksheet("検索結果")
    # ワークシートに要素が書き込まれているかを確認
    # 見出し行（1行目)がない場合
    if worksheet.get_all_values() == [[]]:
        # 見出し行を作成
        worksheet.append_row(["検索日", "キーワード", "タイトル", "URL", "再生回数"])

    length = df_data.shape[0]  # df_dataの行数
    # df_dataにデータが入っている場合（Youtube APIで情報が見つかった場合)
    if length > 0:
        # スプレッドシートに書き出す
        worksheet.update(range_name="A2", values=df_data.astype(str).values.tolist())


if __name__ == "__main__":
    main()
