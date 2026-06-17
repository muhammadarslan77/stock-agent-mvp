import streamlit as st
import yfinance as yf

st.title("Stock Agent MVP")

ticker = st.text_input("Enter Stock Ticker", "AAPL")

if ticker:
    stock = yf.Ticker(ticker)

    try:
        price = stock.history(period="1d")["Close"].iloc[-1]

        st.success(f"Current Price of {ticker}: ${price:.2f}")

    except Exception as e:
        st.error("Could not fetch stock data.")
        