import pandas
import MetaTrader5 as mt5
import pandas as pd
import matplotlib.pyplot as plt
import asyncio
from datetime import datetime
import time

from bot import terminal_status
from bot import terminal_info
from bot import stochastic_indicator
from bot import RSI_indicator
import sys
import os


def bot_release(data_set, stochastic, RSI, UP_level, DOWN_level, lookBack=3, RSI_UP=70, RSI_DOWN=30):
    """
    Реализует работу бота и передает сигналы
    \n: data_set: Принимает значения 
    \n: stochastic: принимает рассчитанные значения stochastic
    \n: RSI: принимает рассчитанные знаечния RSI
    \n: UP_level: Принимает верхнее значение stochastic
    \n: Down_level: Принимает нижнее значение stochastic
    \n: lookBack: глубина проверки истрических данных
    \n: RSI_UP: принимает верхнее значение RSI
    \n: RSI_DOWN: принимает нижнее значение RSI
    """



    # Проверка входных данных
    if stochastic.empty or RSI.empty:
        return None

    try:
        # Безопасное получение значений
        def safe_get(data, col=None):
            if col:
                return data[col].iloc[-1] if isinstance(data, pd.DataFrame) else data.iloc[-1]
            return data.iloc[-1]

        # Получаем последние значения
        d_last = safe_get(stochastic, 'D%')
        rsi_last = safe_get(RSI)
        close_last = safe_get(data_set['close'])
        
        # Проверка сигналов
        was_above_up = any(stochastic['D%'].iloc[-i] > UP_level for i in range(2, lookBack+2))
        was_below_down = any(stochastic['D%'].iloc[-i] < DOWN_level for i in range(2, lookBack+2))

        # Условия
        buy_cond = (d_last >= DOWN_level) and was_below_down and (rsi_last > RSI_DOWN)
        sell_cond = (d_last <= UP_level) and was_above_up and (rsi_last < RSI_UP)

        return 'BUY' if buy_cond else 'SELL' if sell_cond else None

    except Exception as e:
        print(f"Ошибка в bot_release: {str(e)}")
        return None


def profile_status():
    terminal_status()
    account_info = mt5.account_info()

    if account_info is None:
        print("Не удалось получить данные счёта:", mt5.last_error())
    # else:
        # print("Баланс счёта:", account_info.balance)
        # print("Кредитное плечо:", account_info.leverage)
        # print("Валюта счёта:", account_info.currency)
        # print("Свободные средства:", account_info.equity - account_info.margin)

    return account_info


async def bot_settings(
    # настройки по умолчанию 
    botSettings = {
        'Symbol': 'EURUSDrfd',
        'K_periods': 14, 
        'D_periods': 3, 
        'K_slowing': 3, 
        'UP_level': 80, 
        'DOWN_level': 20,
        'RSI_periods': 14,
        'RSI_UP': 70,
        'RSI_DOWN': 30
        }
):
    
    terminal_status()
    
    try:
        data_set = terminal_info(symbol=botSettings['Symbol'])

        async def calculate_stochastic():
            return stochastic_indicator(data_set=data_set, 
                                        K_periods=botSettings['K_periods'], 
                                        D_periods=botSettings['D_periods'],
                                        K_slowing=botSettings['K_slowing'])
        
        async def calculate_rsi():
            return RSI_indicator(data_set=data_set, 
                                periods=botSettings['RSI_periods'])

        stochastic, rsi = await asyncio.gather(
            calculate_stochastic(),
            calculate_rsi(),
            return_exceptions=True  # Для перехвата ошибок
        )

                # Проверка на ошибки в результатах
        if isinstance(stochastic, Exception):
            print(f"Ошибка в Stochastic: {stochastic}")
            return None
        if isinstance(rsi, Exception):
            print(f"Ошибка в RSI: {rsi}")
            return None
        
        return bot_release(
            data_set=data_set,
            stochastic=stochastic,
            RSI=rsi,
            UP_level=botSettings['UP_level'],
            DOWN_level=botSettings['DOWN_level'],
            RSI_UP=botSettings['RSI_UP'],
            RSI_DOWN=botSettings['RSI_DOWN']
        )
    except Exception as e:
        print(f"Ошибка в bot_settings: {e}")
        await asyncio.sleep(5)
        return None
    

def trade(signal=None, balance=None, volume=0.01, symbol='EURUSDrfd'):


    if signal=='SELL':

        lot = balance/1000*volume
        if lot < 0.01:
            lot=0.01
        price = mt5.symbol_info_tick(symbol).bid  # Цена аск для BUY, bid для SELL
        deviation = 10  # Макс. отклонение цены в пунктах

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,  # или ORDER_TYPE_SELL
            "price": price,
            "deviation": deviation,
            "magic": 123456,  # Идентификатор эксперта
            "comment": "Python script open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

        result = mt5.order_send(request)
        print("Полный ответ от MT5:", result._asdict())
        
        input()

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Ошибка исполнения: {result.comment}")
        else:
            print(f"Ордер исполнен: {result.order}")

        with open('trades.log', 'a') as f:
            f.write(f"{datetime.now()}: Signal {signal}, Lot {lot}, Price {price}\n")

    if signal=='BUY':

        lot = balance/1000*volume
        price = mt5.symbol_info_tick(symbol).ask  # Цена аск для BUY, bid для SELL
        deviation = 10  # Макс. отклонение цены в пунктах

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY,  # или ORDER_TYPE_SELL
            "price": price,
            "deviation": deviation,
            "magic": 123456,  # Идентификатор эксперта
            "comment": "Python script open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

        result = mt5.order_send(request)
        # print("Полный ответ от MT5:", result._asdict())  
        # input()

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Ошибка исполнения: {result.comment}")
        else:
            print(f"Ордер исполнен: {result.order}")

        with open('trades.log', 'a') as f:
            f.write(f"{datetime.now()}: Signal {signal}, Lot {lot}, Price {price}\n")    

    if signal is None:
        pass
    return []


async def main_loop():
    balance = profile_status().balance
    botSettings = {
        'Symbol': 'EURUSDrfd',
        'K_periods': 14, 
        'D_periods': 3, 
        'K_slowing': 3, 
        'UP_level': 80, 
        'DOWN_level': 20,
        'RSI_periods': 14,
        'RSI_UP': 70,
        'RSI_DOWN': 30
    }
    
    last_signal = {0: 0}

    while True:
        
        time.sleep(1)
        os.system('cls')
        print(f'-'*100)
        print("Баланс счёта:", profile_status().balance)
        print("Кредитное плечо:", profile_status().leverage)
        print("Валюта счёта:", profile_status().currency)
        print("Свободные средства:", profile_status().equity - profile_status().margin)        
        print(f'последний сигнал {list(last_signal.values())[-1]} ({list(last_signal.keys())[-1]})')
        print(f'-'*100)
        print(f'\n')

        try:
            current_minute = datetime.now().minute
            current_second = datetime.now().second
            
            if current_minute % 15:
                continue

            else:
                
                # Правильный вызов асинхронной функции
                signal = await bot_settings(botSettings=botSettings)
                
                print(f"{datetime.now()}: Получен сигнал - {signal}")
                
                last_signal[datetime.now()] = signal

                if signal is None:
                    print("Нет торгового сигнала")
                    time.sleep(60 - current_second) 
                    continue
                    
                else:        
                    trade(signal=signal, balance=balance)
                    time.sleep(60 - current_second) 

            
        except Exception as e:
            print(f"Ошибка в основном цикле: {e}")
            await asyncio.sleep(5)

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main_loop())