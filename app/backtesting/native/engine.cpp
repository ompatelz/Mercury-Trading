#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

py::dict run_long_only_execution(
    const py::list& timestamps,
    const std::vector<double>& opens,
    const std::vector<double>& closes,
    const std::vector<double>& positions,
    const double initial_capital,
    const double transaction_cost_bps,
    const double slippage_bps) {
  const std::size_t rows = opens.size();
  if (closes.size() != rows || positions.size() != rows || static_cast<std::size_t>(py::len(timestamps)) != rows) {
    throw std::invalid_argument("timestamps, opens, closes, and positions must have the same length");
  }
  if (initial_capital <= 0.0) {
    throw std::invalid_argument("initial_capital must be positive");
  }

  const double fee_rate = transaction_cost_bps / 10000.0;
  const double slippage_rate = slippage_bps / 10000.0;
  double cash = initial_capital;
  double shares = 0.0;
  double entry_cost_basis = 0.0;
  double previous_position = 0.0;
  double turnover_notional = 0.0;
  double transaction_costs = 0.0;
  double slippage_costs = 0.0;
  double equity_sum = 0.0;
  double ending_equity = initial_capital;

  py::list equity_curve;
  py::list trades;

  for (std::size_t index = 0; index < rows; ++index) {
    const double desired_position = positions[index];
    const double open_price = opens[index];
    const double close_price = closes[index];
    const double trade_size = std::abs(desired_position - previous_position);
    double transaction_cost = 0.0;
    double slippage_cost = 0.0;

    if (desired_position > previous_position && cash > 0.0) {
      const double execution_price = open_price * (1.0 + slippage_rate);
      shares = cash / (execution_price * (1.0 + fee_rate));
      const double notional = shares * execution_price;
      transaction_cost = notional * fee_rate;
      slippage_cost = shares * open_price * slippage_rate;
      cash -= notional + transaction_cost;
      entry_cost_basis = notional + transaction_cost;
      turnover_notional += notional;
      transaction_costs += transaction_cost;
      slippage_costs += slippage_cost;

      py::dict trade;
      trade["timestamp"] = timestamps[index];
      trade["side"] = "BUY";
      trade["quantity"] = shares;
      trade["price"] = execution_price;
      trade["notional"] = notional;
      trade["transaction_cost"] = transaction_cost;
      trade["slippage_cost"] = slippage_cost;
      trade["realized_pnl"] = py::none();
      trades.append(trade);
    } else if (desired_position < previous_position && shares > 0.0) {
      const double execution_price = open_price * (1.0 - slippage_rate);
      const double notional = shares * execution_price;
      transaction_cost = notional * fee_rate;
      slippage_cost = shares * open_price * slippage_rate;
      const double realized_pnl = notional - transaction_cost - entry_cost_basis;
      cash += notional - transaction_cost;
      turnover_notional += notional;
      transaction_costs += transaction_cost;
      slippage_costs += slippage_cost;

      py::dict trade;
      trade["timestamp"] = timestamps[index];
      trade["side"] = "SELL";
      trade["quantity"] = shares;
      trade["price"] = execution_price;
      trade["notional"] = notional;
      trade["transaction_cost"] = transaction_cost;
      trade["slippage_cost"] = slippage_cost;
      trade["realized_pnl"] = realized_pnl;
      trades.append(trade);

      shares = 0.0;
      entry_cost_basis = 0.0;
    }

    const double equity = cash + shares * close_price;
    ending_equity = equity;
    equity_sum += equity;

    py::dict row;
    row["timestamp"] = timestamps[index];
    row["cash"] = cash;
    row["shares"] = shares;
    row["trade_size"] = trade_size;
    row["transaction_cost"] = transaction_cost;
    row["slippage_cost"] = slippage_cost;
    row["equity"] = equity;
    equity_curve.append(row);

    previous_position = desired_position;
  }

  const double average_equity = rows == 0 ? initial_capital : equity_sum / static_cast<double>(rows);
  py::dict metrics;
  metrics["number_of_trades"] = static_cast<int>(py::len(trades));
  metrics["turnover"] = average_equity == 0.0 ? 0.0 : turnover_notional / average_equity;
  metrics["transaction_costs"] = transaction_costs;
  metrics["slippage_costs"] = slippage_costs;
  metrics["ending_portfolio_value"] = ending_equity;

  py::dict result;
  result["equity_curve"] = equity_curve;
  result["trades"] = trades;
  result["metrics"] = metrics;
  return result;
}

PYBIND11_MODULE(_engine, module) {
  module.doc() = "Mercury native long-only backtest execution loop";
  module.def(
      "run_long_only_execution",
      &run_long_only_execution,
      py::arg("timestamps"),
      py::arg("opens"),
      py::arg("closes"),
      py::arg("positions"),
      py::arg("initial_capital"),
      py::arg("transaction_cost_bps"),
      py::arg("slippage_bps"));
}
