from gtts import gTTS
import pygame
import io
import time

pygame.mixer.init()

text = "مرحباً يا أصدقائي! أنا فسيلة. هيا نلعب ونتعلم معاً في عالم الفسيلة!"
tts = gTTS(text, lang='ar')

fp = io.BytesIO()
tts.write_to_fp(fp)
fp.seek(0)

pygame.mixer.music.load(fp)
pygame.mixer.music.play()

while pygame.mixer.music.get_busy():
    time.sleep(0.1)

print('Done!')
