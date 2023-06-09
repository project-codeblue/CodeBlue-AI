from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.layers import Embedding, LSTM, Dense ,Dropout
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from tensorflow.keras.callbacks import Callback, LearningRateScheduler, EarlyStopping, ModelCheckpoint
from tensorflow.keras import regularizers
from tensorflow.keras.callbacks import TensorBoard
import numpy as np
import urllib.request
import pandas as pd
from tqdm import tqdm
from konlpy.tag import Okt
import re
import pickle

# TensorBoard 로그 저장 디렉토리 설정
log_dir = "logs"

# TensorBoard 콜백 정의
tensorboard_callback = TensorBoard(log_dir=log_dir)

# 데이터: nsmc 불러오기
urllib.request.urlretrieve("https://raw.githubusercontent.com/e9t/nsmc/master/ratings_train.txt", filename="ratings_train.txt")
urllib.request.urlretrieve("https://raw.githubusercontent.com/e9t/nsmc/master/ratings_test.txt", filename="ratings_test.txt")

# 데이터 분리
train_data = pd.read_table('ratings_train.txt')
test_data = pd.read_table('ratings_test.txt')

# train_data: 데이터 전처리
# document 열과 label 열의 중복을 제외한 값의 개수
train_data['document'].nunique(), train_data['label'].nunique()

# document 열의 중복 제거
train_data.drop_duplicates(subset=['document'], inplace=True)

# Null 값이 존재하는 행 제거
train_data = train_data.dropna(how = 'any') 

# train_data: document 데이터 전처리
train_data['document'] = train_data['document'].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 ]","") # white space 데이터를 empty value로 변경
train_data['document'].replace('', np.nan, inplace=True)

# test_data: 데이터 전처리
test_data.drop_duplicates(subset = ['document'], inplace=True) # document 열에서 중복인 내용이 있다면 중복 제거
test_data['document'] = test_data['document'].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 ]","") # 정규 표현식 수행
test_data['document'] = test_data['document'].str.replace('^ +', "") # 공백은 empty 값으로 변경
test_data['document'].replace('', np.nan, inplace=True) # 공백은 Null 값으로 변경
test_data = test_data.dropna(how='any') # Null 값 제거
print('전처리 후 테스트용 샘플의 개수 :',len(test_data))

# 토큰화
stopwords = ['의','가','이','은','들','는','좀','잘','걍','과','도','를','으로','자','에','와','한','하다']
okt = Okt()

# 토크나이저 저장 경로
tokenizer_path = 'tokenizer.pkl'

# train_data 토큰화
X_train = []
for sentence in tqdm(train_data['document']):
    tokenized_sentence = okt.morphs(sentence, stem=True) # 토큰화
    stopwords_removed_sentence = [word for word in tokenized_sentence if not word in stopwords] # 불용어 제거
    X_train.append(stopwords_removed_sentence)
# print(X_train[:3])

# test_data 토큰화
X_test = []
for sentence in tqdm(test_data['document']):
    tokenized_sentence = okt.morphs(sentence, stem=True) # 토큰화
    stopwords_removed_sentence = [word for word in tokenized_sentence if not word in stopwords] # 불용어 제거
    X_test.append(stopwords_removed_sentence)

# 정수 인코딩
tokenizer = Tokenizer()
tokenizer.fit_on_texts(X_train)

# 등장 빈도수가 3회 미만인 단어들이 이 데이터에서 얼만큼의 비중을 차지하는지 확인
threshold = 3
total_cnt = len(tokenizer.word_index) # 단어의 수
rare_cnt = 0 # 등장 빈도수가 threshold보다 작은 단어의 개수를 카운트
total_freq = 0 # 훈련 데이터의 전체 단어 빈도수 총 합
rare_freq = 0 # 등장 빈도수가 threshold보다 작은 단어의 등장 빈도수의 총 합

# 단어와 빈도수의 쌍(pair)을 key와 value로 받는다.
for key, value in tokenizer.word_counts.items():
    total_freq = total_freq + value

    # 단어의 등장 빈도수가 threshold보다 작으면
    if(value < threshold):
        rare_cnt = rare_cnt + 1
        rare_freq = rare_freq + value

# 전체 단어 개수 중 빈도수 2이하인 단어는 제거.
# 0번 패딩 토큰을 고려하여 + 1
vocab_size = total_cnt - rare_cnt + 1

tokenizer = Tokenizer(vocab_size) 
tokenizer.fit_on_texts(X_train)
X_train = tokenizer.texts_to_sequences(X_train)
X_test = tokenizer.texts_to_sequences(X_test)

# 레이블 데이터 전처리
num_classes = 1
y_train = np.array(train_data['label'])
y_test = np.array(test_data['label'])

# 빈 샘플(empty samples) 제거
drop_train = [index for index, sentence in enumerate(X_train) if len(sentence) < 1]

# 빈 샘플들을 제거
X_train = np.delete(X_train, drop_train, axis=0)
y_train = np.delete(y_train, drop_train, axis=0)

# 패딩
max_len = 30
X_train = pad_sequences(X_train, maxlen=max_len)
X_test = pad_sequences(X_test, maxlen=max_len)

# RNN 모델 구성 (100차원, 활성화 함수:softmax - 다중 클래스 분류에 사용)
embedding_dim = 100
hidden_unit = 128
model = Sequential()
model.add(Embedding(vocab_size, embedding_dim, input_length=max_len))
model.add(LSTM(hidden_unit)) # hidden layer: 조정 대상
# model.add(LSTM(64, kernel_regularizer=regularizers.l1(0.01))) #L1 규제 적용.... 더 떨어짐ㅜ
model.add(Dropout(0.2)) # dropout - 과적합 방지: 조정 대상
model.add(Dense(num_classes, activation='sigmoid'))

# 모델 조기 종료
es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=4)

# 모델 체크포인트 - ModelCheckpoint를 사용하여 검증 데이터의 정확도(val_acc)가 이전보다 좋아질 경우에만 모델을 저장
mc = ModelCheckpoint('test_model.h5', monitor='val_acc', mode='max', verbose=1, save_best_only=True)

# 모델 컴파일 (알고리즘:adam, 손실함수:categorical_crossentropy, 평가지표:accuracy)
model.compile(optimizer='rmsprop', loss='binary_crossentropy', metrics=['acc'])
# model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy']) # 다중 분류시 사용

# # 학습률 스케줄링 함수 정의 (100번동안은 학습률 유지 후 0.1씩 감소 -> 초기학습은 빠르게)
# def lr_scheduler(epoch, lr):
#     if epoch < 1000:
#         return lr
#     else:
#         return lr * 0.1 # learning rate: 조정 대상

# # 학습률 스케줄링 콜백 정의
# lr_scheduler_callback = LearningRateScheduler(lr_scheduler)

# class CustomEarlyStopping(Callback):
#     def __init__(self, accuracy_threshold=0.95, patience=30):
#         super(CustomEarlyStopping, self).__init__()
#         self.accuracy_threshold = accuracy_threshold
#         self.patience = patience
#         self.wait = 0 # 개선 없는 횟수 세기
#         self.stopped_epoch = 0 # 종료 에포크 번호
#         self.best_weights = None # 최적 가중치 저장

#     def on_epoch_end(self, epoch, logs=None):
#         current_accuracy = logs.get('accuracy')

#         if current_accuracy >= self.accuracy_threshold and self.wait >= self.patience:
#             self.stopped_epoch = epoch
#             self.model.stop_training = True
#             print(f"\n조기 종료: 정확도 {self.accuracy_threshold} 이상에 도달하고 {self.patience}번 동안 개선되지 않았습니다.")
#             print(f"{self.patience}번 이전의 모델 가중치로 복원합니다.")
#             self.model.set_weights(self.best_weights)

#         if current_accuracy is not None:
#             if self.best_weights is None or current_accuracy > self.best_accuracy:
#                 self.best_weights = self.model.get_weights()
#                 self.best_accuracy = current_accuracy
#                 self.wait = 0
#             else:
#                 self.wait += 1

# # 조기 종료 콜백 정의 (10번통안 검증손실이 개선되지 않으면 조기종료)
# custom_early_stopping = CustomEarlyStopping(accuracy_threshold=0.95, patience=30)

# 학습 (반복횟수:1000, 한번에 처리할 데이터 샘플:32)
history = model.fit(X_train, y_train, epochs=15, batch_size=64, validation_data=(X_test, y_test), # epochs: 조정 대상
          callbacks=[es, mc, tensorboard_callback], verbose=1)

# 토크나이저 저장
with open(tokenizer_path, 'wb') as f:
    pickle.dump(tokenizer, f)

# 성능 평가
loaded_model = load_model('test_model.h5')
loss, accuracy = loaded_model.evaluate(X_test, y_test)
print("테스트 손실:", loss)
print("테스트 정확도:", accuracy)

# 예측
# sample_symptom = ["환자는 현재 발작성 호흡곤란을 가지고 있고, 약열, 흉통이 있는 상태에서 급성 객혈이 보고되어 숨을 제대로 쉬지 못하는 위급상황입니다."]
# encoded_sample = tokenizer.texts_to_sequences([sample_symptom])
# padded_sample = pad_sequences(encoded_sample, maxlen=max_len, padding='post')
# prediction = model.predict(padded_sample)
# emergency_level = np.argmax(prediction, axis=1) + 1
# print("환자의 응급 정도:", emergency_level)

# 토크나이저 불러오기
with open(tokenizer_path, 'rb') as f:
    tokenizer = pickle.load(f)

def sentiment_predict(new_sentence):
  new_sentence = re.sub(r'[^ㄱ-ㅎㅏ-ㅣ가-힣 ]','', new_sentence)
  new_sentence = okt.morphs(new_sentence, stem=True) # 토큰화
  new_sentence = [word for word in new_sentence if not word in stopwords] # 불용어 제거
  encoded = tokenizer.texts_to_sequences([new_sentence]) # 정수 인코딩 -> 불러온 토크나이저 사용
  pad_new = pad_sequences(encoded, maxlen = max_len) # 패딩
  score = float(loaded_model.predict(pad_new)) # 예측
  if(score > 0.5):
    print("{:.2f}% 확률로 긍정 리뷰입니다.\n".format(score * 100))
  else:
    print("{:.2f}% 확률로 부정 리뷰입니다.\n".format((1 - score) * 100))

sentiment_predict('이 영화 개꿀잼 ㅋㅋㅋ')
sentiment_predict('이 영화 핵노잼 ㅠㅠ')
sentiment_predict('이딴게 영화냐 ㅉㅉ')
sentiment_predict('감독 뭐하는 놈이냐?')