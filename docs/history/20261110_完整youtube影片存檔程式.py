import tkinter as tk  # 匯入 Tkinter，負責建立視窗、按鈕、輸入框
from pytubefix import YouTube  # 匯入 YouTube，用來讀取影片資訊與下載串流
import subprocess  # 用來呼叫 FFmpeg 合併影片和聲音
import os  # 用來處理檔案與資料夾路徑

# ==================== 全域變數 ====================（Global Variables）

yt = None  # 尚未讀取 YouTube 影片。"None"Python 的特殊值，表示目前沒有值 go to line 111
choices = []  # 儲存每個下載格式及其勾選狀態
loaded_url = ""  # 記錄成功讀取格式的網址，先建立一個空的變數，準備記住你上一次成功讀取影片格式時使用的 YouTube 網址。

# ==================== 讀取影片格式 ====================

def loadFormats():  # 定義讀取格式的函式
    global yt, choices, loaded_url  # 允許修改函式外的這三個變數 line 8,9,10

    labelMsg.config(text="正在讀取影片格式...")  # 顯示讀取狀態 line 313
    win.update_idletasks()  # 更新等待處理的畫面工作，畫面暫時性更新

    for widget in frameOptions.winfo_children():  # 取得格式區域裡的所有舊元件 上一個的line 279。.winfo_children()取得 frameOptions 裡面所有直接子元件
        widget.destroy()  # 刪除舊元件，避免重複顯示

    choices = []  # 清空舊的格式清單
    yt = None  # 清除上一支影片
    loaded_url = ""  # 清除上一支影片的網址

    if url.get().strip() == "":  # 讀取網址，.strip()去除前後空白後檢查是否為空 lead to line 216
        labelMsg.config(text="請先輸入 YouTube 網址")  # 顯示提醒 lead to 313
        return  # 結束函式

    try:  # 嘗試讀取影片
        current_url = url.get().strip()  # 取得目前輸入的網址
        yt = YouTube(current_url)  # 建立 YouTube 影片物件

        video_streams = yt.streams.filter(  # 篩選影片串流
            only_video=True,  # 只要純影像，不包含聲音
            subtype="mp4"  # 只選 MP4 容器的影像
        ).order_by("resolution").desc()  # 依解析度由高到低排列

        audio_streams = yt.streams.filter(  # 篩選音訊串流
            only_audio=True  # 只要純音訊
        )  # 完成音訊篩選

        tk.Label(  # 建立影片格式區的標題
            frameOptions,  # 放進格式選擇區 line 279
            text="影片格式（下載後使用 FFmpeg 合併音訊）"  # 顯示標題
        ).pack(anchor="w")  # 靠左顯示

        for stream in video_streams:  # 逐一處理每個影片格式 line 35
            selected = tk.IntVar(value=0)  # 建立勾選變數，0 是未勾選

            title = (  # 組合格式說明文字
                str(stream.resolution) + " / " +  # 解析度，例如 2160p
                str(stream.subtype) + " / " +  # 容器格式，例如 mp4
                str(stream.fps) + " fps / " +  # 影格率
                str(stream.video_codec)  # 影像編碼格式
            )  # 完成格式說明

            cb = tk.Checkbutton(  # 建立勾選框
                frameOptions,  # 放在格式選擇區
                text=title,  # 顯示剛才組合的文字
                variable=selected  # 連接 selected，記錄勾選狀態 lead to line 50
            )  # 完成勾選框

            cb.pack(anchor="w")  # 靠左顯示勾選框

            choices.append(("video", stream, selected))  # 記錄影片類型、串流及勾選變數 line 23

        tk.Label(  # 建立純音訊區標題
            frameOptions,  # 放在格式選擇區
            text="純音訊格式"  # 顯示文字
        ).pack(anchor="w", pady=(12, 0))  # 靠左顯示，增加上方間距

        for stream in audio_streams:  # 逐一處理純音訊格式
            selected = tk.IntVar(value=0)  # 每個音訊格式都有獨立勾選變數

            title = (  # 組合音訊格式說明
                str(stream.subtype) + " / " +  # 容器格式
                str(stream.abr) + " / " +  # 標示音訊位元率
                str(stream.audio_codec)  # 音訊編碼格式
            )  # 完成音訊說明

            cb = tk.Checkbutton(  # 建立音訊勾選框
                frameOptions,  # 放在格式選擇區
                text=title,  # 顯示音訊格式說明
                variable=selected  # 連接勾選變數
            )  # 完成勾選框

            cb.pack(anchor="w")  # 靠左顯示

            choices.append(("audio", stream, selected))  # 記錄音訊串流與勾選狀態

        loaded_url = current_url  # 記錄成功讀取格式的網址
        labelMsg.config(text="格式讀取完成，請勾選要下載的項目")  # 顯示完成訊息

    except Exception as error:  # 如果讀取過程發生錯誤
        yt = None  # 清除影片物件
        choices = []  # 清除選項資料
        loaded_url = ""  # 清除網址紀錄

        for widget in frameOptions.winfo_children():  # 取得可能已建立的選項元件
            widget.destroy()  # 清除不完整的選項

        labelMsg.config(text="讀取失敗：" + str(error))  # 顯示錯誤原因


# ==================== 下載影片或音訊 ====================

def clickDown():  # 定義下載函式，與下載按鈕的 command 連接

    if yt is None:  # 如果尚未讀取影片
        labelMsg.config(text="請先讀取影片格式")  # 顯示提醒
        return  # 停止執行

    if url.get().strip() != loaded_url:  # 檢查網址是否在讀取格式後被更改 lead to line 93
        labelMsg.config(text="網址已更改，請重新讀取影片格式")  # 提醒重新讀取
        return  # 停止執行

    selected_choices = []  # 建立清單，儲存真正勾選的項目

    for kind, stream, selected in choices:  # 逐一檢查格式與勾選變數
        if selected.get() == 1:  # 如果勾選狀態是 1
            selected_choices.append((kind, stream))  # 加入待下載清單 lead to 119

    if len(selected_choices) == 0:  # 如果沒有勾選任何項目
        labelMsg.config(text="請至少勾選一個格式")  # 顯示提醒
        return  # 停止執行

    pathdir = path.get().strip()  # 取得儲存路徑

    if pathdir == "":  # 如果儲存路徑留空
        pathdir = os.path.expanduser("~/Downloads")  # 使用 Mac 的下載項目資料夾
    else:  # 如果有指定路徑
        pathdir = os.path.expanduser(pathdir)  # 展開路徑中的 ~

#下載前的準備工作
    try:  # 嘗試執行下載
        os.makedirs(pathdir, exist_ok=True)  # 確保儲存資料夾存在

#尋找之後要與純影像串流合併的音訊。
        merge_audio = yt.streams.filter(  # 尋找合併影片要用的音訊
            only_audio=True,  # 只要純音訊
            subtype="mp4"  # 使用 MP4 類型音訊
        ).order_by("abr").desc().first()  # 取得標示位元率最高的串流

        for kind, stream in selected_choices:  # 逐一下載已勾選的格式

            if kind == "audio":  # 如果是純音訊
                labelMsg.config(text="正在下載音訊...")  # 顯示下載狀態
                win.update_idletasks()  # 更新畫面

                extension = stream.subtype  # 取得音訊容器格式

                if extension == "mp4":  # 如果音訊容器是 MP4
                    extension = "m4a"  # 使用 m4a 副檔名

                filename = (  # 建立音訊檔名
                    "audio_" + str(stream.itag) + "." + extension  # 加入 itag 避免不同格式互相覆蓋
                )  # 完成檔名

                stream.download(  # 下載音訊
                    output_path=pathdir,  # 儲存資料夾
                    filename=filename  # 指定檔名
                )  # 完成下載呼叫

            elif kind == "video":  # 如果是影片

                if merge_audio is None:  # 如果找不到可以合併的音訊
                    raise RuntimeError("找不到可合併的 MP4 音訊")  # 產生錯誤

                labelMsg.config(text="正在下載影像與音訊...")  # 更新狀態
                win.update_idletasks()  # 更新畫面

                video_path = stream.download(  # 下載純影像
                    output_path=pathdir,  # 儲存資料夾
                    filename="temp_video_" + str(stream.itag) + ".mp4"  # 影像暫存檔名
                )  # 將實際檔案路徑存入 video_path

                audio_path = merge_audio.download(  # 下載純音訊
                    output_path=pathdir,  # 儲存資料夾
                    filename="temp_audio_" + str(stream.itag) + ".m4a"  # 音訊暫存檔名
                )  # 將實際檔案路徑存入 audio_path

                output_path = os.path.join(  # 組合輸出檔案的完整路徑
                    pathdir,  # 儲存資料夾
                    "video_" + str(stream.resolution) +  # 解析度
                    "_" + str(stream.itag) + ".mp4"  # 串流編號及副檔名
                )  # 完成輸出路徑

                labelMsg.config(text="正在使用 FFmpeg 合併...")  # 更新狀態
                win.update_idletasks()  # 更新畫面

                subprocess.run([  # 呼叫 FFmpeg
                    "ffmpeg",  # 執行 FFmpeg 程式
                    "-y",  # 允許覆蓋已存在的輸出檔案
                    "-i", video_path,  # 第一個輸入檔案：純影像
                    "-i", audio_path,  # 第二個輸入檔案：純音訊
                    "-map", "0:v:0",  # 選取第一個輸入檔案的第一條影像串流
                    "-map", "1:a:0",  # 選取第二個輸入檔案的第一條音訊串流
                    "-c", "copy",  # 不重新編碼，直接複製串流
                    output_path  # 合併後的輸出檔案
                ], check=True)  # 如果 FFmpeg 執行失敗，產生例外錯誤

                os.remove(video_path)  # 合併成功後刪除影像暫存檔
                os.remove(audio_path)  # 合併成功後刪除音訊暫存檔

        labelMsg.config(text="已完成勾選項目的下載")  # 全部完成後顯示訊息

    except Exception as error:  # 如果下載或合併過程發生錯誤
        labelMsg.config(text="下載失敗：" + str(error))  # 顯示錯誤原因

# ==================== 建立主視窗 ====================

win = tk.Tk()  # 建立 Tkinter 主視窗
win.geometry("750x650")  # 設定視窗寬度 750、高度 650
win.title("YouTube 影片備份")  # 設定視窗標題

url = tk.StringVar()  # 儲存網址輸入框的文字
path = tk.StringVar()  # 儲存路徑輸入框的文字

# ==================== 網址輸入區 ====================

frame1 = tk.Frame(win)  # 建立網址區塊
frame1.pack(pady=12)  # 顯示區塊並增加上下間距

tk.Label(frame1, text="YouTube 網址：").pack(side=tk.LEFT)  # 建立網址說明標籤".pack(side=tk.LEFT)"它告訴 pack()：把元件沿著容器的左側開始排列。

entryURL = tk.Entry(  # 建立Entry用來輸入網址
    frame1,  # 放在 frame1 裡
    textvariable=url,  # 連接最上方的 url 變數 lead to Line 216
    width=55,  # 設定輸入匡寬度
    state="normal"  # 使用正常可編輯狀態
).pack(side=tk.LEFT)# 顯示網址輸入框


# ==================== 儲存路徑輸入區 ====================

frame2 = tk.Frame(win)  # 建立儲存路徑區塊
frame2.pack(pady=8)  # 顯示區塊並增加上下間距

tk.Label(  # 建立儲存路徑標籤
    frame2,  # 放在 frame2 裡
    text="儲存路徑（留空＝Mac 下載項目）："  # 顯示預設路徑說明
).pack(side=tk.LEFT)  # 靠左顯示

entrypath = tk.Entry(  # 建立儲存路徑輸入框
    frame2,  # 放在 frame2 裡
    textvariable=path,  # 連接最上方的 path 變數 to line 217
    width=45,  # 設定寬度
    state="normal"  # 使用正常可編輯狀態
).pack(side=tk.LEFT)  # 顯示儲存路徑輸入框


# ==================== 讀取格式按鈕，在 Tkinter 視窗中建立一個「讀取影片格式」按鈕，當你按下按鈕時，就執行 loadFormats() 函式。

btnLoad = tk.Button(  # 建立讀取格式按鈕
    win,  # 放在主視窗
    text="讀取影片格式",  # 按鈕文字
    command=loadFormats  # 按下後執行 loadFormats() to line 14
)

btnLoad.pack(pady=10)  # 顯示按鈕


# ==================== 可捲動的格式選擇區，建立一個可以上下捲動的區域，讓使用者勾選 YouTube 提供的不同影片畫質與音訊格式。

outerFrame = tk.Frame(win)  # 建立格式區域的外層容器
outerFrame.pack(fill="both", #讓元件填滿分配給它的水平與垂直空間
                expand=True,#當視窗有多餘空間時，讓這個元件參與分配
                padx=20)

#Canvas 可以理解成 Tkinter 的「畫布」，它可以放置圖形、文字，甚至其他 Tkinter 元件，這裡利用他的捲動功能
canvas = tk.Canvas(outerFrame)  # 建立可捲動的 Canvas

scrollbar = tk.Scrollbar(  # 建立捲軸
    outerFrame,  # 放在外層容器
    orient="vertical",  # 設定垂直捲軸
    command=canvas.yview  # 讓捲軸控制，這是已經定義好的函式， 
) 

frameOptions = tk.Frame(canvas)  # 建立放置格式勾選框的容器放在可以捲動的canvas畫布裡面

#當 frameOptions 裡面的勾選框增加、減少，導致容器尺寸改變時，自動更新 Canvas 可以捲動的範圍。
frameOptions.bind(  # .bind()偵測格式容器的配置或尺寸變化
    "<Configure>",  # 當 frameOptions 的配置或尺寸改變時，執行後面的動作。
    lambda event: canvas.configure(  # lambda 也可以建立函式，只是它適合用來寫簡短的動作。canvas.configure()修改 Canvas（畫布）的設定
        scrollregion=canvas.bbox("all")  # 讓可捲動範圍符合內容大小，bbox 是 Bounding Box（邊界框）
    ) )
canvas.create_window(  # 在 Canvas 裡放入格式容器
    (0, 0),  # 放在左上角座標
    window=frameOptions,  # 指定放入 frameOptions
    anchor="nw"  # 使用左上角作為定位基準
)  # 完成容器放置

canvas.configure(yscrollcommand=scrollbar.set)  # yscrollcommand=指定 Canvas 垂直捲動位置變化時，要通知哪個函式，scrollbar.set	Scrollbar 內建的方法，負責更新捲軸滑塊

canvas.pack(side=tk.LEFT, fill="both", expand=True)  # 顯示 Canvas
scrollbar.pack(side=tk.RIGHT, fill="y")  # 顯示右側捲軸


# ==================== 下載按鈕 ====================

btnDown = tk.Button(  # 建立下載按鈕
    win,  # 放在主視窗
    text="下載勾選的格式",  # 按鈕文字
    command=clickDown,  # 按下後執行 clickDown()
    width=35  # 設定按鈕寬度
)  # 完成下載按鈕

btnDown.pack(pady=12)  # 顯示下載按鈕


# ==================== 狀態訊息 ====================

labelMsg = tk.Label(  # 建立訊息標籤
    win,  # 放在主視窗
    text="請輸入網址並讀取格式",  # 初始訊息
    fg="red",  # 文字顏色為紅色
    wraplength=700  # 訊息太長時自動換行
)  # 完成訊息標籤

labelMsg.pack(pady=8)  # 顯示訊息標籤

win.mainloop()  # 啟動 Tkinter 事件迴圈，讓視窗可以接收操作
