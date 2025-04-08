# 必要なモジュールをimport
import pandas as pd
from apiclient.discovery import build
import datetime as dt
import gspread
from google.oauth2.service_account import Credentials
import math


def main():
    #2つのAPIを記述しないとリフレッシュトークンを3600秒毎に発行し続けなければならない
    scope = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
    #認証情報設定
    #ダウンロードしたjsonファイル名をクレデンシャル変数に設定
    credentials = Credentials.from_service_account_file("***************.json", scopes=scope)
    #OAuth2の資格情報を使用してGoogle APIにログインします。
    gc = gspread.authorize(credentials)
    #共有設定したスプレッドシートキーを変数[SPREADSHEET_KEY]に格納する。
    SPREADSHEET_KEY = '************************************'

    #共有設定したスプレッドシートの検索キーワードシートを開く
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('検索キーワード')
    keyword_list = worksheet.col_values(1)

    api_key = '************************************'
    # 今から24時間前の時刻-utc時刻
    fromtime = (dt.datetime.utcnow()-dt.timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
    # videourlの設定
    videourl = 'https://www.youtube.com/watch?v='
    # データを入れる空のリストを作成
    data = []

    # キーワードリストを元に検索
    for keyword in keyword_list:
        nextpagetoken = ''
        youtube = build('youtube','v3',developerKey=api_key)

        # nextPageTokenがあるまで動画データを取得
        while True:
            # youtube.search
            result = youtube.search().list(
                part='snippet',
                #検索したい文字列を指定
                q=keyword,
                #1回の試行における最大の取得数
                maxResults = 50,
                #視聴回数が多い順に取得
                order='viewCount',
                #いつから情報を検索するか？
                publishedAfter = fromtime,
                #動画タイプ
                type='video',
                #地域コード
                regionCode = 'JP',
                #ページ送りのトークンの設定
                pageToken=nextpagetoken
            ).execute()

            # もしも動画数が50件より少ないならば、dataに情報を追加してbreak
            if len(result['items']) < 50:
                for i in result['items']:
                    data.append([i['id']['videoId'],i['snippet']['publishedAt'],i['snippet']['title'],keyword])
                break
            # もしも動画数が50件より多い場合はページ送りのトークン(result['nextPageToken']を変数nextpagetokenに設定する
            else:
                for i in result['items']:
                    data.append([i['id']['videoId'],i['snippet']['publishedAt'],i['snippet']['title'],keyword])
                nextpagetoken = result['nextPageToken']   

            # data = [[videoId, 投稿日, タイトル, 検索キーワード], [videoId, 投稿日, タイトル, 検索キーワード]...]         

    videoid_list = []
    for i in data:
        videoid_list.append(i[0])
    videoid_list = sorted(set(videoid_list),key=videoid_list.index)

    # 50のセットの数(次のデータ取得で最大50ずつしかデータが取れないため、50のセットの数を数えている)
    data_length = len(data)
    _set_50 = math.ceil(data_length/50)

    _id_list = []
    for i in range(_set_50):
        _id_list.append(','.join(videoid_list[i*50:(i*50+50)]))

    # 再生回数データを取得
    viewcount_list = []
    for videoid in _id_list:
        # youtube.videos
        viewcount = youtube.videos().list(
                        part='statistics',
                        maxResults = 50,
                        id = videoid
                    ).execute()
        
        for i in viewcount['items']:
            viewcount_list.append([i['id'],i['statistics']['viewCount']])
            
    # データフレームの作成
    df_data = pd.DataFrame(data,columns=['videoid','publishtime','title','keyword'])
    # 重複の削除 subsetで重複を判定する列を指定,inplace=Trueでデータフレームを新しくするかを指定
    df_data.drop_duplicates(subset='videoid',inplace=True)
    # 動画のURL
    df_data['url'] = videourl +  df_data['videoid']
    # 調査した日
    df_data['search_day'] = dt. date.today().strftime('%Y/%m/%d')
    df_viewcount = pd.DataFrame(viewcount_list,columns=['videoid','viewcount'])
    
    # 2つのデータフレームのマージ
    df_data = pd.merge(df_viewcount, df_data,on='videoid',how='left')
    # viewcountの列のデータを条件検索のためにint型にする(元データも変更)
    df_data['viewcount'] =  df_data['viewcount'].astype(int)
    # データフレームの条件を満たす行だけを抽出
    df_data =  df_data.query('viewcount>=100000')
    
    # viewcountの列のデータをint型から文字列型に戻している
    df_data = df_data[['search_day','keyword','title','url','viewcount']]
    df_data['viewcount'] =  df_data['viewcount'].astype(str)
    

    #共有設定したスプレッドシートの検索結果シートを開く
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('検索結果')

    last_row = len(worksheet.get_all_values())
    if last_row == 0:
        cell_columns = worksheet.range('A1:E1')
        cell_columns[0].value = '検索日'
        cell_columns[1].value = '検索キーワード'
        cell_columns[2].value = 'Title'
        cell_columns[3].value = 'URL'
        cell_columns[4].value = '再生回数(検索時)'
        worksheet.update_cells(cell_columns)
        last_row += 1
    length = df_data.shape[0]
    if length == 0:
        pass
    else:

        cell_list = worksheet.range('A{0}:E{1}'.format(last_row+1,last_row+length))
        for cell in cell_list:
            cell.value = df_data.iloc[cell.row-last_row-1][cell.col-1]

        # スプレッドシートに書き出す
        worksheet.update_cells(cell_list)

if __name__=='__main__':
    main()