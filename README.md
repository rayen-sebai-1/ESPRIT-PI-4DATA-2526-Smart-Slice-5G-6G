# Smart Slice Selection in 5G/6G

## Overview
This project was developed as part of the 4th Year DATA Engineering Program at **Esprit School of Engineering** (Academic Year 2025-2026). 

The evolution of mobile communication from 5G to 6G demands dynamic resource management to handle heterogeneous services with strict Quality of Service (QoS) requirements. This project aims to leverage data analytics and machine learning to replace static, semi-manual network slicing policies with intelligent, predictive models. By accurately forecasting network conditions and service requirements, the system dynamically assigns the most appropriate network slice (eMBB, URLLC, mMTC) to optimize resource utilization and protect Service Level Agreements (SLAs).

## Features
* **Predictive Resource Contention:** Time-series forecasting to anticipate congestion in CPU, bandwidth, and memory 5 to 15 minutes in advance.
* **QoS Adherence Likelihood Regression:** Probabilistic risk scoring to estimate the confidence level that a slice assignment will satisfy strict QoS constraints.
* **Adaptive Online Learning:** Continuous model adaptation to evolving traffic patterns and new topologies (like SAGIN) without full batch retraining.
* **Explainable AI (XAI):** Integration of frameworks (e.g., SHAP, LIME) to provide transparent, human-readable explanations for automated slice selection decisions.
* **Decision Intelligence Dashboard:** A centralized, real-time interface monitoring slice assignments, QoS metrics, and SLA adherence probabilities.

## Tech Stack
### Frontend
* `To be completed`

### Backend
* Python, FastAPI, PyTorch / Scikit-Learn 
* Data manipulation & XAI: `[e.g., Pandas, SHAP, LIME]`

## Architecture
* Used a synthetic dataset for 6G and a real world 5G dataset
* We generated other dataset using the initial datasets and simpy

## Contributors
* Ahmed Bouhlel
* Rayen Sebai
* Mouhamed Dhia Chaouachi
* Fourat Hamdi
* Mouhamed Aziz Weslati
* Mouhamed Aziz Boughanmi


## Academic Context
Developed at **Esprit School of Engineering - Tunisia** 
* **Module:** Projet Intégré (4ème année DATA)
* **Group:** Azerty67
* **Academic Year:** 2025/2026

## Getting Started
`git clone https://github.com/rayen-sebai-1/ESPRIT-PI-4DATA-2526-Smart-Slice-5G-6G.git`

## Acknowledgments
We would like to express our gratitude to our mentors Rahma Bouraoui, Safa Cherif, and Ameni Mejri for their guidance and support throughout this project.