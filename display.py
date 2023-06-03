import os, time, sys
from koch_trainer import KochTrainerAudioGen

class ColorfulCharacterDisplay:
    def __init__(self, text):
        self.text = text
        self.index = 0

    def display_character(self, character):
        if os.name == 'nt':
            # For Windows
            os.system('cls')
        else:
            # For UNIX-based systems (Linux, macOS)
            os.system('clear')

        bright_yellow = "\033[1;33m"
        bright_red = "\033[1;31m"
        reset = "\033[0m"
        output = bright_yellow + self.text[:self.index] + bright_red + self.text[self.index] 
        print(output)

    def next(self):
        if self.index >= len(self.text):
            return False

        character = self.text[self.index]
        if character.isalnum():
            koch_audio = KochTrainerAudioGen(character)
            koch_audio.emit_audio()
        else:
            koch_audio = KochTrainerAudioGen(' ')
            koch_audio.emit_audio()
  
        self.display_character(character)
        self.index += 1
        return True
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide the text to display as a command-line argument.")
        sys.exit(1)

    text = sys.argv[1]
    text = text.upper()
    display = ColorfulCharacterDisplay(text)
    if os.name == 'nt':
        # For Windows
        os.system('cls')
    else:
        # For UNIX-based systems (Linux, macOS)
        os.system('clear')

    time.sleep(3)
    more = True
    while more:
        more = display.next()

    time.sleep(3)
