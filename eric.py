import random
import tkinter as tk
from tkinter import messagebox
import os

#choice,setup,game,end

num = 0
Min = 0
Max = 0
count = 0
difficulty = 100
bestscore=0
def casual():
    frame_choice.pack_forget()#part1 hide  
    frame_setup.pack(pady=20)#part2 appear
    entry_guess.delete(0, tk.END)#guess number auestion hide
    entry_min.delete(0, tk.END)#clean the Min answer
    entry_max.delete(0, tk.END)#clean the Max answer
def competitive():
    entry_guess.delete(0, tk.END)#guess number auestion hide
    frame_choice.pack_forget()#part1 hide
    frame_choice2.pack(pady=20)#part1.5 appear
def start_competitive_game(max_range):
    global num, Min, Max, count,difficulty
    
    difficulty = max_range
    Min = 1
    Max = max_range
    num = random.randint(Min, Max)
    count = 0
    
    label_range.config(text=f"{Min} ~ {Max}, choice a number")
    label_hint.config(text=f"🏆 Mode: 1 ~ {max_range}",font=("Arial", 20), fg="green")
    frame_choice2.pack_forget()
    frame_game.pack(pady=20) 
def load_best_record(max_range):#read records
    filename = f"best_{max_range}.txt"
    if os.path.exists(filename):
        with open(filename, "r") as f:
            content = f.read().strip()
            return int(content) if content else None
    return None
def save_best_record(max_range, score):#store records
    filename = f"best_{max_range}.txt"
    with open(filename, "w") as f:
        f.write(str(score))
def start_game():
    global num, Min, Max, count
    min_val = entry_min.get()
    max_val = entry_max.get()
    
    if not min_val.isdigit() or not max_val.isdigit():
        messagebox.showerror("Error", "input error,positive number only")
        return
        
    Min = int(min_val)
    Max = int(max_val)
    
    if Max < Min:
        messagebox.showerror("Error", "input error(Max can't smaller than Min)")
    elif Max == Min:
        messagebox.showerror("Error", "input error(Max can't be like Min)")
    else:
        num = random.randint(Min, Max)
        count = 0
        label_range.config(text=f"{Min} ~ {Max}, choice a number")
        frame_setup.pack_forget()#part2 hide  
        frame_game.pack(pady=20)#part3 appear

def guess_number():
    global Min, Max, count
    A = entry_guess.get()
    
    if not A.isdigit():
        messagebox.showerror("Error", "input error,positive number only")
        return
        
    A = int(A)
    count += 1

    if A == num:
        frame_game.pack_forget()#part3 hide  
        frame_end.pack(pady=20)#part4 
        best_score = load_best_record(difficulty)
        if best_score is None or count < best_score:
            save_best_record(difficulty, count)
            label_end.config(text=f"🎉 NEW RECORD! 🎉\nCorrect, you win!\nYou guessed {count} times.", fg="gold")
        else:
            label_end.config(text=f"Correct, you win!\nYou guessed {count} times.\n(Best: {best_score} times)", fg="blue")
    else:
        if A > num:
            if A <= Max:
                label_hint.config(text="wrong answer, Be smaller",font=("Arial", 20), fg="red")
                Max = A
            else:
                messagebox.showwarning("Warning", "Input error((out of range))")
        else:
            if A >= Min:
                label_hint.config(text="wrong anwser, Be bigger",font=("Arial", 20), fg="blue")
                Min = A
            else:
                messagebox.showwarning("Warning", "input error(out of range)")
                
        label_range.config(text=f"{Min} ~ {Max}, choice a number")
        entry_guess.delete(0, tk.END) 

def reset_game():
    frame_end.pack_forget()#part4 hide
    entry_guess.delete(0, tk.END)#guess number auestion hide
    label_hint.config(text="")#wrong answer text hide
    if entry_min.get() == "": 
        frame_choice2.pack(pady=20)
    else:
        frame_setup.pack(pady=20)#part2 appear
        entry_min.delete(0, tk.END)#clean the Min answer
        entry_max.delete(0, tk.END)#clean the Max answer
window = tk.Tk()#Construction Interface
window.title("Guess Number")
window.geometry("400x280")
frame_choice = tk.Frame(window)#PART1 background
frame_choice.pack(pady=20)

label_choice= tk.Label(frame_choice, text="Welcome to the number guessing game", font=("Arial",13, "bold"))#part4 text
label_choice.grid(row=0, column=0, columnspan=2, pady=10)

label2_choice= tk.Label(frame_choice, text="Which mode would you like to play?", font=("Arial",13))#part4 text
label2_choice.grid(row=1, column=0, columnspan=2, pady=10)

btn_choice= tk.Button(frame_choice, text="casual", command=casual, font=("Arial", 20))
btn_choice.grid(row=2, column=0, pady=10)

btn_choice2= tk.Button(frame_choice, text="competitive", command=competitive, font=("Arial", 20))
btn_choice2.grid(row=2, column=1, pady=10)
#----------------------------------------------------------------------------------------
frame_choice2=tk.Frame(window)#part1.5

tk.Button(frame_choice2, text="Level 1 (1 ~ 100)", font=("Arial", 14), command=lambda: start_competitive_game(100)).pack(pady=5, fill="x")
tk.Button(frame_choice2, text="Level 2 (1 ~ 1000)", font=("Arial", 14), command=lambda: start_competitive_game(1000)).pack(pady=5, fill="x")
tk.Button(frame_choice2, text="Level 3 (1 ~ 10000)", font=("Arial", 14), command=lambda: start_competitive_game(10000)).pack(pady=5, fill="x")
btn_clear = tk.Button(frame_choice, text="Clear Records", font=("Arial", 10),#clean record
                      command=lambda: (
                          os.path.exists("best_100.txt") and os.remove("best_100.txt"),
                          os.path.exists("best_1000.txt") and os.remove("best_1000.txt"),
                          os.path.exists("best_10000.txt") and os.remove("best_10000.txt"),
                          messagebox.showinfo("Success", "All records cleared!")
                      ))
btn_clear.grid(row=3, column=0, columnspan=2, pady=10)
tk.Button(frame_choice2, text="Back", font=("Arial", 10), 
          command=lambda: (frame_choice2.pack_forget(), frame_choice.pack(pady=20))).pack(pady=10)
#----------------------------------------------------------------------------------------
frame_setup = tk.Frame(window)#PART2 backgroun

tk.Label(frame_setup, text="Min:",font=("Arial", 30)).grid(row=0, column=0, padx=5, pady=5)#min?
entry_min = tk.Entry(frame_setup, width=10)
entry_min.grid(row=0, column=1, padx=5, pady=5)

tk.Label(frame_setup, text="Max:",font=("Arial", 30)).grid(row=1, column=0, padx=5, pady=5)#max?
entry_max = tk.Entry(frame_setup, width=10)
entry_max.grid(row=1, column=1, padx=5, pady=5)

btn_start = tk.Button(frame_setup, text="Start Game", command=start_game,font=("Arial", 25))#part2 button
btn_start.grid(row=2, column=0, columnspan=2, pady=10)
#----------------------------------------------------------------------------------------
frame_game = tk.Frame(window)#part3 background
label_range = tk.Label(frame_game, text="", font=("Arial", 20, "bold"))#part3 text
label_range.pack(pady=5)

entry_guess = tk.Entry(frame_game, width=15, font=("Arial", 20))#guess number auestion
entry_guess.pack(pady=5)

btn_guess = tk.Button(frame_game, text="Guess!", command=guess_number, width=10,font=("Arial", 20))#check answer
btn_guess.pack(pady=5)

label_hint = tk.Label(frame_game, text="", font=("Arial", 10))#wrong answer text
label_hint.pack(pady=5)
#-----------------------------------------------------------------------------------------
frame_end= tk.Frame(window)#part4 background
label_end= tk.Label(frame_end, text="", font=("Arial", 20, "bold"),fg="blue")#part4 text
label_end.grid(row=0, column=0, columnspan=2, pady=10)

btn_again = tk.Button(frame_end, text="again!", command=reset_game,font=("Arial", 20))#again button
btn_again.grid(row=1, column=0, pady=10)

btn_return = tk.Button(frame_end, text="back",command=lambda: (frame_end.pack_forget(), frame_choice.pack(pady=20)), font=("Arial", 20))#return bytton
btn_return.grid(row=1, column=1, pady=10)

btn_exit = tk.Button(frame_end, text="Exit", command=window.destroy, font=("Arial", 10))#leave bytton
btn_exit.grid(row=2, column=0,columnspan=2, pady=10)

window.mainloop()
