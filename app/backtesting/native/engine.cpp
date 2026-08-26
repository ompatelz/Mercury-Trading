#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

namespace {

struct Trade {
  std::size_t index;
  std::string side;
  double quantity;
  double price;
  double notional;
  double transaction_cost;
  double slippage_cost;
  double realized_pnl;
  bool closes_position;
};

py::array_t<double> to_array(const std::vector<double>& values) {
  py::array_t<double> result(values.size());
  auto output = result.mutable_unchecked<1>();
  for (std::size_t index = 0; index < values.size(); ++index) output(index) = values[index];
  return result;
}

void validate_input(const py::array_t<double, py::array::c_style>& values, const char* name,
                    py::ssize_t expected_size, bool prices) {
  if (values.ndim() != 1) throw std::invalid_argument(std::string(name) + " must be one-dimensional");
  if (expected_size >= 0 && values.shape(0) != expected_size)
    throw std::invalid_argument("opens, closes, and positions must have the same length");
  auto input = values.unchecked<1>();
  for (py::ssize_t index = 0; index < input.shape(0); ++index)
    if (!std::isfinite(input(index)) || (prices && input(index) <= 0.0))
      throw std::invalid_argument(std::string(name) + (prices ? " must contain finite positive prices" : " must contain finite values"));
}

}  // namespace

py::dict run_long_only_execution(const py::array_t<double, py::array::c_style>& opens,
                                 const py::array_t<double, py::array::c_style>& closes,
                                 const py::array_t<double, py::array::c_style>& positions,
                                 double initial_capital, double transaction_cost_bps,
                                 double slippage_bps) {
  validate_input(opens, "opens", -1, true);
  validate_input(closes, "closes", opens.shape(0), true);
  validate_input(positions, "positions", opens.shape(0), false);
  if (!std::isfinite(initial_capital) || initial_capital <= 0.0)
    throw std::invalid_argument("initial_capital must be finite and positive");
  if (!std::isfinite(transaction_cost_bps) || transaction_cost_bps < 0.0 ||
      !std::isfinite(slippage_bps) || slippage_bps < 0.0)
    throw std::invalid_argument("transaction_cost_bps and slippage_bps must be finite and non-negative");

  auto open_values = opens.unchecked<1>();
  auto close_values = closes.unchecked<1>();
  auto position_values = positions.unchecked<1>();
  const auto rows = static_cast<std::size_t>(opens.shape(0));
  const double fee_rate = transaction_cost_bps / 10000.0;
  const double slippage_rate = slippage_bps / 10000.0;
  double cash = initial_capital, shares = 0.0, entry_cost_basis = 0.0, previous_position = 0.0;
  double turnover_notional = 0.0, transaction_costs = 0.0, slippage_costs = 0.0, equity_sum = 0.0;
  std::vector<double> cash_curve(rows), shares_curve(rows), trade_sizes(rows), transaction_curve(rows), slippage_curve(rows), equity_curve(rows);
  std::vector<Trade> trades;

  for (std::size_t index = 0; index < rows; ++index) {
    const double desired_position = position_values(index), open_price = open_values(index), close_price = close_values(index);
    const double trade_size = std::abs(desired_position - previous_position);
    double transaction_cost = 0.0, slippage_cost = 0.0;
    if (desired_position > previous_position && cash > 0.0) {
      const double execution_price = open_price * (1.0 + slippage_rate);
      shares = cash / (execution_price * (1.0 + fee_rate));
      const double notional = shares * execution_price;
      transaction_cost = notional * fee_rate;
      slippage_cost = shares * open_price * slippage_rate;
      cash -= notional + transaction_cost;
      entry_cost_basis = notional + transaction_cost;
      turnover_notional += notional; transaction_costs += transaction_cost; slippage_costs += slippage_cost;
      trades.push_back({index, "BUY", shares, execution_price, notional, transaction_cost, slippage_cost, 0.0, false});
    } else if (desired_position < previous_position && shares > 0.0) {
      const double execution_price = open_price * (1.0 - slippage_rate);
      const double notional = shares * execution_price;
      transaction_cost = notional * fee_rate;
      slippage_cost = shares * open_price * slippage_rate;
      const double realized_pnl = notional - transaction_cost - entry_cost_basis;
      cash += notional - transaction_cost;
      turnover_notional += notional; transaction_costs += transaction_cost; slippage_costs += slippage_cost;
      trades.push_back({index, "SELL", shares, execution_price, notional, transaction_cost, slippage_cost, realized_pnl, true});
      shares = 0.0; entry_cost_basis = 0.0;
    }
    const double equity = cash + shares * close_price;
    cash_curve[index] = cash; shares_curve[index] = shares; trade_sizes[index] = trade_size;
    transaction_curve[index] = transaction_cost; slippage_curve[index] = slippage_cost; equity_curve[index] = equity;
    equity_sum += equity; previous_position = desired_position;
  }

  py::list trade_rows;
  for (const Trade& trade : trades) {
    py::dict row;
    row["index"] = trade.index; row["side"] = trade.side; row["quantity"] = trade.quantity;
    row["price"] = trade.price; row["notional"] = trade.notional; row["transaction_cost"] = trade.transaction_cost;
    row["slippage_cost"] = trade.slippage_cost;
    if (trade.closes_position) {
      row["realized_pnl"] = trade.realized_pnl;
    } else {
      row["realized_pnl"] = py::none();
    }
    trade_rows.append(row);
  }
  const double average_equity = rows == 0 ? initial_capital : equity_sum / static_cast<double>(rows);
  py::dict metrics;
  metrics["number_of_trades"] = static_cast<int>(trades.size()); metrics["turnover"] = average_equity == 0.0 ? 0.0 : turnover_notional / average_equity;
  metrics["transaction_costs"] = transaction_costs; metrics["slippage_costs"] = slippage_costs;
  metrics["ending_portfolio_value"] = rows == 0 ? initial_capital : equity_curve.back();
  py::dict result;
  result["cash"] = to_array(cash_curve); result["shares"] = to_array(shares_curve); result["trade_size"] = to_array(trade_sizes);
  result["transaction_cost"] = to_array(transaction_curve); result["slippage_cost"] = to_array(slippage_curve); result["equity"] = to_array(equity_curve);
  result["trades"] = trade_rows; result["metrics"] = metrics;
  return result;
}

PYBIND11_MODULE(_engine, module) {
  module.doc() = "Mercury native long-only backtest execution loop";
  module.def("run_long_only_execution", &run_long_only_execution, py::arg("opens"), py::arg("closes"), py::arg("positions"), py::arg("initial_capital"), py::arg("transaction_cost_bps"), py::arg("slippage_bps"));
}
