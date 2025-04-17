# 必要なモジュールをimport
import pandas as pd
import math
from apiclient.discovery import build
import datetime as dt
import gspread
from google.oauth2.service_account import Credentials
# 形態素解析をするためのjanomeをインストール
from janome.tokenizer import Tokenizer

def main():
    # 2つのAPIを記述しないとリフレッシュトークンを3600秒毎に発行し続けなければならない
    scope = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
    # 認証情報設定
    # ダウンロードしたjsonファイル名をクレデンシャル変数に設定
    credentials = Credentials.from_service_account_file("***************.json", scopes=scope)
    # OAuth2の資格情報を使用してGoogle APIにログインします。
    gc = gspread.authorize(credentials)
    # 共有設定したスプレッドシートキーを変数[SPREADSHEET_KEY]に格納する。
    SPREADSHEET_KEY = '************************************'
    # 共有設定したスプレッドシートの検索キーワードシートを開く
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('検索キーワード')
    keyword_list = worksheet.col_values(1)

    # Youtube APIキーの記入
    api_key = '************************************'
    # 今から24時間前の時刻をfromtimeとする（今の時刻のタイムゾーンはYoutubeに合わせて協定世界時刻のutcにする)
    fromtime = '2020-01-01T00:00:00Z'

    # データを入れる空のリストを作成
    data = []
    # キーワードリストを元に検索
    for keyword in keyword_list:
        nextpagetoken = ''
        youtube = build('youtube','v3', developerKey=api_key)
    
        # while文でnextPageTokenがあるまで動画データを取得
        while True:
            # youtube.search().listで動画情報を取得。結果は辞書型
            result = youtube.search().list(
                # 必須パラメーターのpart
                part='snippet',
                # 検索したい文字列を指定
                q=keyword,
                # 1回の試行における最大の取得数
                maxResults=50,
                #視聴回数が多い順に取得
                order='viewCount',
                #いつから情報を検索するか？
                publishedAfter=fromtime,
                #動画タイプ
                type='video',
                #地域コード
                regionCode='JP',
                #ページ送りのトークンの設定
                pageToken=nextpagetoken
            ).execute()

            # もしも動画数が50件以下ならば、dataに情報を追加してbreak
            if len(result['items']) < 50:
                for i in result['items']:
                    data.append([i['id']['videoId'], i['snippet']['publishedAt'], i['snippet']['title'], keyword])
                break
            # もしも動画数が50件より多い場合はページ送りのトークン(result['nextPageToken']を変数nextpagetokenに設定する
            else:
                for i in result['items']:
                    data.append([i['id']['videoId'], i['snippet']['publishedAt'], i['snippet']['title'], keyword])
                nextpagetoken = result['nextPageToken']

            # data = [[videoId, 投稿日, 動画タイトル, 検索キーワード], [videoId, 投稿日, 動画タイトル, 検索キーワード], ...]              
            # datalength = len(data)
    # videoidリストを作成
    videoid_list = []
    for i in data:
        videoid_list.append(i[0])
    # videoidリストの中の重複を取り除く
    videoid_list = sorted(set(videoid_list), key=videoid_list.index)

    # data_lengthをlen(data)と置く
    data_length = len(data)
    # 50のセットの数(次のデータ取得で最大50ずつしかデータが取れないため、50のセットの数を数えている)
    # math.ceilは小数点以下は繰り上げの割り算　例　math.ceil(3.4) = 4
    _set_50 = math.ceil(data_length/50)

    _id_list = []
    for i in range(_set_50):
        _id_list.append(','.join(videoid_list[i*50:(i*50+50)]))
    # 再生回数データを取得して、再生回数リストを作成
    viewcount_list = []
    for videoid in _id_list:
        viewcount = youtube.videos().list(
                        part='statistics',
                        maxResults=50,
                        id=videoid
                    ).execute()
        for i in viewcount['items']:
            viewcount_list.append([i['id'],i['statistics']['viewCount']])

    # 動画情報を入れたデータフレームdf_dataの作成
    df_data = pd.DataFrame(data, columns=['videoid', 'publishtime', 'title', 'keyword'])
    # 重複の削除 subsetで重複を判定する列を指定,inplace=Trueでデータフレームを新しくするかを指定,
    df_data.drop_duplicates(subset='videoid',inplace=True)
    # 動画のURL
    df_data['url'] = 'https://www.youtube.com/watch?v=' + df_data['videoid']
    # 調査した日
    df_data['search_day'] = dt.date.today().strftime('%Y/%m/%d')
    # 再生回数データを入れたデータフレームdf_viewcountの作成
    df_viewcount = pd.DataFrame(viewcount_list, columns=['videoid', 'viewcount'])
    # 2つのデータフレームのマージ
    df_data = pd.merge(df_viewcount, df_data, on='videoid', how='left')

    # viewcountの列のデータを条件検索のためにint型にする(元データも変更)
    df_data['viewcount'] = df_data['viewcount'].astype(int)

    # データフレームのviewcountに記載されている、再生回数が条件を満たす行だけを抽出
    df_data = df_data.query('viewcount>=500000')

    # viewcountの列のデータをint型から文字列型に戻している
    df_data['viewcount'] = df_data['viewcount'].astype(str)
    df_data = df_data[['search_day', 'keyword', 'title', 'url', 'viewcount']]

    # 極性辞書をPythonの辞書にしていく
    np_dic = {}
    
    with open("pn.csv.m3.120408.trim", "r", encoding="utf-8") as f:  # 日本語評価極性辞書のファイルの読み込み
        lines = [line.replace('\n', '').split('\t') for line in f.readlines()] # 1行1行を読み込み、文字列からリスト化。リストの内包表記の形に

    posi_nega_df = pd.DataFrame(lines, columns = ['word', 'score', 'explain'])  # リストからデータフレームの作成
    
    # データフレームの2つの列から辞書の作成　zip関数を使う
    np_dic = dict(zip(posi_nega_df.word, posi_nega_df.score))

    # 形態素解析をするために必要な記述を書いていく
    tokenizer = Tokenizer()

    # Youtubeのタイトル一つ一つを入れてあるデータフレームの列（本文の列）をsentensesと置く
    sentences = df_data['title']
            
    # p,n,e,?p?nを数えるための辞書を作成
    result = {'p': 0, 'n': 0, 'e': 0, '?p?n': 0}

    # スプレッドシートにPとNの列を追加するために空のリストを用意
    posi_list = []
    nega_list = []

    for sentence in sentences:  # タイトルを一つ一つ取り出す
        for token in tokenizer.tokenize(sentence):  # 形態素解析をする部分
                word = token.surface # ツイートに含まれる単語を抜き出す
                if word in np_dic:  # 辞書のキーとして単語があるかどうかの存在確認
                    value = np_dic[word]  # 値(pかnかeか?p?nのどれか)をvalueという文字で置く
                    if value in result:  # キーの存在確認
                        result[value] += 1  # p,n,eの個数を数える
                        
        summary = result['p'] + result['n'] + result['e'] + result['?p?n']  #総和を求める

        # ネガポジ度の平均を数値でそれぞれ出力
        try:
            posi_list.append(result['p'] / summary)  # ポジティブ度の平均のリスト
            nega_list.append(result['n'] / summary)  #　ネガティブ度の平均のリスト

        except ZeroDivisionError:  # summaryが0の場合
            print("None Value")
            posi_list.append(0)
            nega_list.append(0)

    # df_dataにPとNの列を追加
    df_data['P'] = posi_list
    df_data['N'] = nega_list

    df_data = df_data[['search_day', 'keyword', 'title', 'P' ,'N', 'url', 'viewcount']]

    #共有設定したスプレッドシートの検索結果シートを開く
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('検索結果')
    # ワークシートに要素が書き込まれているかを確認
    last_row = len(worksheet.get_all_values())
    # 見出し行（1行目)がない場合
    if last_row == 0:
        cell_columns = worksheet.range('A1:G1')
        cell_columns[0].value = '検索日'
        cell_columns[1].value = '検索キーワード'
        cell_columns[2].value = 'Title'
        cell_columns[3].value = 'P'
        cell_columns[4].value = 'N'        
        cell_columns[5].value = 'URL'
        cell_columns[6].value = '再生回数(検索時)'
        worksheet.update_cells(cell_columns)
        last_row += 1
    # もしdf_dataにデータが入っていない場合は書き込みをpass（Youtube APIで情報が取得されなかった場合)
    length = df_data.shape[0] # df_dataの行数
    if length == 0:
        pass
    # df_dataにデータが入っている場合（Youtube APIで情報が見つかった場合)
    else:
        cell_list = worksheet.range(f'A{last_row+1}:G{last_row+length}')
        for cell in cell_list:
            cell.value = df_data.iloc[cell.row-last_row-1][cell.col-1]
        # スプレッドシートに書き出す
        worksheet.update_cells(cell_list)

if __name__ == '__main__':
    main()
