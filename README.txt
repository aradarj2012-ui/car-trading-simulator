# Car Trading Simulator

**Video Demo:** [Add your video URL here]  
**Author:** [Arad Arj]  
**GitHub:** [Your GitHub username or repository URL]  
**edX:** [Your edX username]  
**Location:** [Kashan, Iran]  
**Date:** [Submission Date]

## About me 
hello , I'm Arad and I'm 14 years old programmer , i really liked the CS50 lessons and i learned new things although it was a bit hard :O , my goal was to get the python certification so i can use it in the future , before learning CS50's python I've learned python before for like 2 years so lets say i programmed most of the first projects with my own knowledge :) . for the final project I got help from AI , he made the "cars.json" file and also helped with the themes and colors of "interface.py" and organized my coding a bit and the name of the variables (if AI wasn't available my coding would look like my own dirty room :/)

## Description
Car Trading Simulator is a desktop game developed in Python for the CS50P Final Project.

The player starts with a limited amount of money and builds a car collection by purchasing vehicles from a car store. Cars have different prices and spawn probabilities, so some vehicles are much rarer than others.

The goal is to build a valuable car collection, manage money, purchase upgrades, and operate a personal car shop.
## Features

- **Car Store:** Browse available cars and purchase them.
- **Random Stock:** The store displays a selection of cars based on their spawn probabilities.
- **Restock Timer:** The store refreshes after a set amount of time.
- **Garage:** Store and manage owned vehicles.
- **My Shop:** Put cars up for sale and receive customer offers.
- **Upgrades:** Purchase upgrades to improve different parts of the business.
- **Creator Code:** Redeem a creator code for an in-game reward.
- **Save System:** Save game progress and load it when the game starts again.

## Project Files

- `project.py` — Main program and game logic.
- `interface.py` — Graphical user interface built with Tkinter.
- `test_project.py` — Tests for the main functions.
- `requirements.txt` — Required Python packages.
- `data/cars.json` — Car catalog, prices, and spawn probabilities.
- `assets/cars/` — Car images.
- `saves/` — Saved game progress.

## Requirements

- Python 3
- Tkinter
- Packages listed in `requirements.txt`

## Installation

Install the required packages:

```bash
python -m pip install -r requirements.txt
```

## How to Run

Run the following command from the project directory:

```bash
python project.py
```

## Running Tests

Run the tests using pytest:

```bash
python -m pytest test_project.py
```

## Design Decisions

I separated the game logic from the graphical interface to make the project easier to organize and maintain.

The car catalog is stored in a JSON file so that car information, prices, and spawn probabilities can be changed without editing the main game logic.

The save system allows players to continue their progress between sessions.