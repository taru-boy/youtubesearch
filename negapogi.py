# 形態素解析をするためのjanomeをインストール
from janome.tokenizer import Tokenizer

# pandas
import pandas as pd

def negapogi(df):
    '''
    データフレームを引数に受け取り、
    ネガポジ分析をする関数
    '''
    # 極性辞書をPythonの辞書にしていく
    np_dic = {}
    
    with open("pn.csv.m3.120408.trim", "r", encoding="utf-8") as f:  # 日本語評価極性辞書のファイルの読み込み
        lines = [line.replace('\n', '').split('\t') for line in f.readlines()] # 1行1行を読み込み、文字列からリスト化。リストの内包表記の形に

    posi_nega_df = pd.DataFrame(lines, columns = ['word', 'score', 'explain'])  # リストからデータフレームの作成
    
    # データフレームの2つの列から辞書の作成　zip関数を使う
    np_dic = dict(zip(posi_nega_df.word, posi_nega_df.score))

    # 形態素解析をするために必要な記述を書いていく
    tokenizer = Tokenizer()

    # ツイート一つ一つを入れてあるデータフレームの列（本文の列）をsentensesと置く
    sentenses = df['本文']
            
    # p,n,e,?p?nを数えるための辞書を作成
    result = {'p': 0, 'n': 0, 'e': 0, '?p?n': 0}
    
    for sentence in sentenses:  # ツイートを一つ一つ取り出す
        for token in tokenizer.tokenize(sentence):  # 形態素解析をする部分
                word = token.surface # ツイートに含まれる単語を抜き出す
                if word in np_dic:  # 辞書のキーとして単語があるかどうかの存在確認
                    value = np_dic[word]  # 値(pかnかeか?p?nのどれか)をvalueという文字で置く
                    if value in result:  # キーの存在確認
                        result[value] += 1  # p,n,eの個数を数える
                        
    summary = result['p'] + result['n'] + result['e'] + result['?p?n']  #総和を求める

    # ネガポジ度の平均を数値でそれぞれ出力
    try:
        print("posi:", result['p'] / summary)  # ポジティブ度の平均
        print("nega", result['n'] / summary)  #　ネガティブ度の平均
    except ZeroDivisionError:  # summaryが0の場合
        print("None Value")