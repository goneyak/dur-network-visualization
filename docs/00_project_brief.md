# DUR Risk Map

## One-Sentence Definition
This project turns public Korean DUR data into an interactive ingredient-level risk network for exploring known contraindication rules.

## Project Goal
The main goal is to make drug risk rules easier to inspect by showing how drugs are connected through co-administration contraindications and related DUR warning categories.

## What this project does
- Visualizes contraindicated drug pairs as a network.
- Adds supporting rule layers such as pregnancy contraindications, elderly cautions, and age-specific restrictions.
- Helps users inspect cumulative known risk signals in polypharmacy scenarios.

## What this project does not do
- It does not predict new adverse events.
- It does not replace clinical judgment or prescribing systems.
- It does not claim patient-specific medical safety recommendations.

## MVP Scope
- Build a contraindication graph from the AC file.
- Support ingredient search and selection.
- Show directly connected contraindicated ingredients.
- Display the reason text attached to each contraindication edge.

## Out of Scope for the First Version
- Full patient-level decision support.
- Automated risk scoring validated for clinical use.
- Complete coverage of every DUR rule type in the interface.