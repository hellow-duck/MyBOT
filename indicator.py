import MetaTrader5 as mt5
from datetime import datetime
from datetime import timedelta
import pandas as pd
import pytz
import matplotlib.pyplot as plt
import numpy as np
import os


def terminal_status():
    
    terminal_path = r'C:\\Program Files\\MetaTrader 5 Alfa-Forex\\terminal64.exe'
    if not mt5.initialize(terminal_path):
        print("terminal_status: Не удалось инициализировать MetaTrader 5:", mt5.last_error())
        exit()

    # else:
    #     print("terminal_status: Состояние терминала: \n", mt5.terminal_info())
    #     # print("Сервер:", mt5.terminal_info().server)
    #     print("terminal_status: Соединение: \n", mt5.terminal_info().connected)

def terminal_info(symbol):
    """
    Принимает символ, по которому будет собрана информация
    : symbol: символ
    """    
    time_zone = pytz.timezone('UTC')

    # # Проверка есть ли символа в базе
    # # В будущем при реализации интерфеса можно убрать, так как список доступных символов будет отображаться уже в самом интерфейсе
    # # Проверка не нужна
    # #--------------------------------------------------------------------------------------------
    # avail_symbol = mt5.symbols_get()
    # avail = []
    # for i in avail_symbol:
    #     i = i[-1].split('\\')
    #     avail.append(i[-1])

    # if symbol not in avail:
    #     print('terminal_status: Данного символа нет в базе')
    #     exit()
    # #--------------------------------------------------------------------------------------------

    timeFrame= mt5.TIMEFRAME_M15

    # Получаем текущую дату в UTC
    now = datetime.now(time_zone)

    # Устанавливаем диапазон дат
    toDate = now.date()
    fromDate = (now - timedelta(days=14)).date()

    # Преобразуем в datetime с временной зоной
    from_datetime = time_zone.localize(datetime.combine(fromDate, datetime.min.time()))
    to_datetime = time_zone.localize(datetime.combine(toDate, datetime.max.time()))

    print(fromDate)
    print(toDate)

    if not mt5.symbol_select(symbol, True):
        print(f"terminal_status: Не удалось выбрать символ {symbol}: {mt5.last_error()}")
        mt5.shutdown()
        exit()

    rates = mt5.copy_rates_range(symbol, timeFrame, from_datetime, to_datetime)

    if rates is None:
        print("terminal_status: Не удалось получить данные:", mt5.last_error())
        return []
    else:
        rates_df = pd.DataFrame(rates)
        return rates_df

def stochastic_indicator(data_set=None, K_periods=9, D_periods=3, K_slowing=9):
    """
    \n : data_set: принимает исторические данные 
    \n : K_periods: 9 
    \n : D_periods: 3 
    \n : K_slowing: 9 
    """
    if data_set is None:
        print('Stochastic_indicator: Нет данных для расчета')
        exit()

    close = data_set['close'].values
    low = data_set['low'].values
    high = data_set['high'].values
    size = len(close)

    stochastic_value = {}
    

    # Инициализация массивов
    minLow = np.full(size, np.nan)
    maxHigh = np.full(size, np.nan)
    k = np.full(size, np.nan)
    d = np.full(size, np.nan)
    kSlow = np.full(size, np.nan)

    # Расчёт min/max вручную (быстрее sliding_window_view для N < 30)
    for i in range(K_periods-1, size):
        minLow[i] = np.min(low[i-K_periods+1:i+1])
        maxHigh[i] = np.max(high[i-K_periods+1:i+1])

    # расчет K%
    valid = ~np.isnan(minLow)
    k[valid] = (close[valid] - minLow[valid]) / (maxHigh[valid] - minLow[valid]) * 100
    
    # Применяем замедление (K_slowing)
    for i in range(K_periods-1 + K_slowing-1, size):
        window = slice(i-K_slowing+1, i+1)
        kSlow[i] = np.mean(k[window])
    
    # 4. Расчёт %D (сглаженный K_slow)
    for i in range(K_periods-1 + K_slowing-1 + D_periods-1, size):
        window = slice(i-D_periods+1, i+1)
        d[i] = np.mean(kSlow[window])
    
    # Возврат в DataFrame
    stochastic_value['K%'] = k
    stochastic_value['K%_slowing'] = kSlow
    stochastic_value['D%'] = d

    df = pd.DataFrame(stochastic_value)
    
    return df

def RSI_indicator(data_set=None, periods=14):
    """
    Расчитывает значения графика RSI
    : data_set: Принимает исторические данные
    : periods: 14
    """
    
    close = data_set['close']
    close_delta = close.diff()

    result = pd.DataFrame({
        'delta': close_delta,
        'plus': np.where(close_delta > 0, close_delta, 0),
        'minus': np.where(close_delta < 0, abs(close_delta), 0)
    })

    ema_up = np.full(len(result), np.nan)
    ema_down = np.full(len(result), np.nan)
    RSI = np.full(len(result), np.nan)

    alpha = 2/(periods+1)

    # Первое значение EMA (SMA)
    first_ema_idx = periods-1  # Для periods=14 это 13
    ema_up[first_ema_idx] = np.mean(result['plus'][:periods])
    ema_down[first_ema_idx] = np.mean(result['minus'][:periods])

    # Расчет EMA
    for i in range(first_ema_idx+1, len(result)):
        ema_up[i] = result['plus'].iloc[i] * alpha + ema_up[i-1] * (1-alpha)
        ema_down[i] = result['minus'].iloc[i] * alpha + ema_down[i-1] * (1-alpha)


    result['ema_up'] = ema_up
    result['ema_down'] = ema_down


    # Безопасный расчет RS
    result['rs'] = np.where(
        ema_down != 0,
        ema_up / ema_down,
        np.nan
    )

    # Расчет RSI - начинаем С ТОГО ЖЕ ИНДЕКСА, что и EMA
    for i in range(first_ema_idx, len(result)):
        if not np.isnan(result['rs'].iloc[i]):
            RSI[i] = 100 - (100 / (1 + result['rs'].iloc[i]))

        result['RSI'] = RSI
    
    return result['RSI']

def check_signal(dPeriod, lookBack=3, UP_level=80, DOWN_level=20):

    checkUP = any(dPeriod[-i] > UP_level for i in range(2, lookBack + 2))
    checkDOWN = any(dPeriod[-i] < DOWN_level for i in range(2, lookBack + 2))

    return checkUP, checkDOWN