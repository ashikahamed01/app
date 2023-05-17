from flask import Flask, send_file
import logging
import math
import statistics
from scipy.io import wavfile
import music21
from pydub import AudioSegment
import crepe
from collections import defaultdict
from mido import MidiFile
from pydub.generators import Sine

logger = logging.getLogger()
logger.setLevel(logging.ERROR)

app = Flask(__name__)

A4 = 440
C0 = A4 * pow(2, -4.75)
note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def hz2offset(freq):
    if freq == 0: 
        return None
    h = round(12 * math.log2(freq / C0))
    return 12 * math.log2(freq / C0) - h

def quantize_predictions(group, ideal_offset):
    non_zero_values = [v for v in group if v != 0]
    zero_values_count = len(group) - len(non_zero_values)

    if zero_values_count > 0.8 * len(group):
        return 0.51 * len(non_zero_values), "Rest"
    else:
        h = round(statistics.mean([12 * math.log2(freq / C0) - ideal_offset for freq in non_zero_values]))
        octave = h // 12
        n = h % 12
        note = note_names[n] + str(octave)
        error = sum([abs(12 * math.log2(freq / C0) - ideal_offset - h)for freq in non_zero_values])
        return error, note


def get_quantization_and_error(pitch_outputs_and_rests, predictions_per_eighth,prediction_start_offset, ideal_offset):
    pitch_outputs_and_rests = [0] * prediction_start_offset + pitch_outputs_and_rests

    groups = [pitch_outputs_and_rests[i:i + predictions_per_eighth] for i in range(0, len(pitch_outputs_and_rests), predictions_per_eighth)]
    quantization_error = 0

    notes_and_rests = []
    for group in groups:
        error, note_or_rest = quantize_predictions(group, ideal_offset)
        quantization_error += error
        notes_and_rests.append(note_or_rest)

    return quantization_error, notes_and_rests

@app.route('/')
def hello_world():
    print()
    uploaded_file_name = 'c-scale.wav'
    sr, audio = wavfile.read('input.wav')
    time, frequency, confidence, activation = crepe.predict(audio, sr, viterbi=True, step_size=35)
    indices = range(len (frequency))
    print(confidence, frequency)
    pitch_outputs_and_rests = [
        p if c >= 0 else 0
        for i, p, c in zip(indices, frequency, confidence)
    ]
    
    offsets = [hz2offset(p) for p in pitch_outputs_and_rests if p != 0]
    print("offsets: ", offsets)

    ideal_offset = statistics.mean(offsets)
    print("ideal offset: ", ideal_offset)

    best_error = float("inf")
    best_notes_and_rests = None
    best_predictions_per_note = None

    for predictions_per_note in range(20, 65, 1):
        for prediction_start_offset in range(predictions_per_note):
            error, notes_and_rests = get_quantization_and_error(pitch_outputs_and_rests, predictions_per_note,prediction_start_offset, ideal_offset)
            if error < best_error:      
                best_error = error
                best_notes_and_rests = notes_and_rests
                best_predictions_per_note = predictions_per_note
    while best_notes_and_rests[0] == 'Rest':
        best_notes_and_rests = best_notes_and_rests[1:]
    while best_notes_and_rests[-1] == 'Rest':
        best_notes_and_rests = best_notes_and_rests[:-1]

    sc = music21.stream.Score()
    bpm = 60 * 60 / best_predictions_per_note
    a = music21.tempo.MetronomeMark(number=bpm)
    sc.insert(0,a)

    for snote in best_notes_and_rests:   
        d = 'half'
        if snote == 'Rest':      
            sc.append(music21.note.Rest(type=d))
        else:
            sc.append(music21.note.Note(snote, type=d))

    print(best_notes_and_rests)
    converted_audio_file_as_midi = 'output.mid'
    fp = sc.write('midi', fp=converted_audio_file_as_midi)
    #wav_from_created_midi = "output.wav"
    #fpw = sc.write('wav', fpw=wav_from_created_midi)
    convmidtowav()   
    return send_file('E:\Main Project\output.wav')

def convmidtowav():
    
    def note_to_freq(note, concert_A=440.0):
        return (2.0 ** ((note - 69) / 12.0)) * concert_A

    mid = MidiFile("E:\Main Project\output.mid")
    output = AudioSegment.silent(mid.length * 1000.0)

    tempo = 100 # bpm

    def ticks_to_ms(ticks):
        tick_ms = (60000.0 / tempo) / mid.ticks_per_beat
        return ticks * tick_ms
  

    for track in mid.tracks:
        # position of rendering in ms
        current_pos = 0.0

        current_notes = defaultdict(dict)
        # current_notes = {
        #   channel: {
        #     note: (start_time, message)
        #   }
        # }
  
        for msg in track:
            current_pos += ticks_to_ms(msg.time)

            if msg.type == 'note_on':
                current_notes[msg.channel][msg.note] = (current_pos, msg)
    
            if msg.type == 'note_off':
                start_pos, start_msg = current_notes[msg.channel].pop(msg.note)
  
                duration = current_pos - start_pos
  
                signal_generator = Sine(note_to_freq(msg.note))
                rendered = signal_generator.to_audio_segment(duration=duration-50, volume=-20).fade_out(100).fade_in(30)

                output = output.overlay(rendered, start_pos)

    output.export("output1.wav", format="wav")

'''@app.route('/play')
def play_midi():
    port = mido.open_output()
    mid = mido.MidiFile('E:\Main Project\output.mid')
    for msg in mid.play():
        port.send(msg)'''

if __name__ == '__main__':
    app.run()


''' json_file = []
    # json_file.append('hello_world')
    # return jsonify(json_file)'''
