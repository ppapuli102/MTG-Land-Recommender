# import main

def CreateGUI():    
    import tkinter as tk

    # Create the main window
    window = tk.Tk()

    # Set window title
    window.title("Land Suggestor")

    # Create a label and set its text
    label = tk.Label(text="MtGA Deck Import")
    label.pack()

    # Create an input text box
    text_box = tk.Entry(text="1 Plains\n1 Island\n1 Swamp\n1 Mountain\n1 Forest", width=50)
    text_box.pack()

    # Retreive the text entered by the user
    def retreive_text():
        global imported_deck
        imported_deck = text_box.get()
        # main.ConvertDeckList(imported_deck)

    # Create a button and set its text
    button = tk.Button(text="Import", command=retreive_text)
    button.pack()

    # Start the main loop
    window.mainloop()

# def GetDeckList():
#     return deck_list

if __name__ == '__main__':
    CreateGUI()