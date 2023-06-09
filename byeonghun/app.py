from konlpy.tag import Okt
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten
from gensim.models import Word2Vec
from keras.models import load_model
import numpy as np
from datas import data

# text = '''예전에도 오른쪽 머리 부분의 통증 병력(+)
# 1DA 오른쪽 머리 뒷 부분의 통증 발생,
# 콕콕 쑤시는 양상.
# 최근에 감기에 걸렸으며, 약간의 오심(+).
# 약을 먹지 는 않.
# 신경을 약간 쓰는 편임.'''

# 응급 정도 레이블
labels = [4, 2, 3, 1]

# model = load_model('./model/save.h5')

# 문장 토큰화
for texts in data:
    okt = Okt()
    sentences = [okt.morphs(text) for text in texts]

    # 불용 제거
    stopwords = ['부분', '약간', '편임', '의']
    filtered_sentences = [[word for word in sentence if word not in stopwords] for sentence in sentences]

    # Word2Vec 모델 학습 (100차원, 주변 단어고려:3, 최소단어빈도:1, 스레드:4, skip-gram(1)알고리즘 사용. CBOW(0)으로 변경 가능)
    embedding_model = Word2Vec(filtered_sentences, vector_size=100, window=3, min_count=1, workers=4, sg=1)

    # 벡터화된 문장 획득
    tokenizer = Tokenizer()
    tokenizer.fit_on_texts(filtered_sentences)
    encoded_sentences = tokenizer.texts_to_sequences(filtered_sentences)
    padded_sentences = pad_sequences(encoded_sentences, padding='post')

    # 응급 정도 레이블을 배열로 변환
    labels = np.array(labels)

    # 모델 구성
    model = Sequential()
    model.add(Flatten(input_shape=(padded_sentences.shape[1],))) 
    model.add(Dense(64, activation='relu')) # 입력노드 64, 활성화 함수 ReLU
    model.add(Dense(5, activation='softmax')) # 출력노드 5(응급도가 5단계니까), 활성화 함수 softmax 

    # 모델 컴파일 (알고리즘:adam, 손실함수:categorical_crossentropy, 평가지표:accuracy)
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

    # 모델 학습 (반복횟수:10, 한번에 처리할 데이터 샘플:32)
    model.fit(padded_sentences, labels, epochs=10, batch_size=32)

    # 새로운 환자 상태 입력
    new_text = "밤에 가슴이 답답하고 호흡이 어려움"

    # 입력 문장 전처리
    new_sentence = okt.morphs(new_text)
    filtered_new_sentence = [word for word in new_sentence if word not in stopwords]
    encoded_new_sentence = tokenizer.texts_to_sequences([filtered_new_sentence])
    padded_new_sentence = pad_sequences(encoded_new_sentence, maxlen=padded_sentences.shape[1], padding='post')

    # 응급 정도 예측
    prediction = model.predict(padded_new_sentence)
    emergency_level = np.argmax(prediction) + 1
    print("환자의 응급 정도:", emergency_level)

model.save('./model/save.h5')
