`include "define.v"

//
// 32-bit multi-cycle divider (trial subtraction / restoring division).
//
// Replaces the single-cycle behavioural `/` and `%` that previously lived in
// ex.v.  Those synthesised into a ~280 ns combinational carry chain, which put
// the whole sys_clk domain at ~3.5 MHz against a 25 MHz clock.  Here the work
// is spread over 32 clocks and the pipeline is held with stallreq_from_ex,
// so the critical path becomes a single 32-bit subtract.
//
// Handshake:
//   start_i  held high by EX while a DIV/DIVU is in flight
//   ready_o  pulses high when result_o is valid; EX then drops start_i
//   annul_i  abort (pipeline flush) -- returns to idle immediately
//
// result_o = { remainder[63:32], quotient[31:0] }
//
module div (
    input  wire                 clk,
    input  wire                 rst,

    input  wire                 signed_div_i,   // 1 = DIV (signed), 0 = DIVU
    input  wire[`RegBus]        opdata1_i,      // dividend
    input  wire[`RegBus]        opdata2_i,      // divisor
    input  wire                 start_i,
    input  wire                 annul_i,

    output reg[`DoubleRegBus]   result_o,
    output reg                  ready_o
);

    localparam DivFree   = 2'b00;
    localparam DivByZero = 2'b01;
    localparam DivOn     = 2'b10;
    localparam DivEnd    = 2'b11;

    reg [1:0]  state;
    reg [5:0]  cnt;        // 0..32 iterations
    reg [64:0] dividend;   // { remainder , quotient } shift register
    reg [31:0] divisor;

    // partial remainder minus divisor; bit 32 is the borrow flag
    wire [32:0] div_temp = {1'b0, dividend[63:32]} - {1'b0, divisor};

    // signed division operates on magnitudes, signs are reapplied at the end
    wire [31:0] abs_op1 = (signed_div_i && opdata1_i[31]) ? (~opdata1_i + 32'd1) : opdata1_i;
    wire [31:0] abs_op2 = (signed_div_i && opdata2_i[31]) ? (~opdata2_i + 32'd1) : opdata2_i;

    always @(posedge clk) begin
        if (rst == `RstEnable) begin
            state    <= DivFree;
            ready_o  <= 1'b0;
            result_o <= {`ZeroWord, `ZeroWord};
            cnt      <= 6'd0;
            dividend <= 65'd0;
            divisor  <= 32'd0;
        end else begin
            case (state)

                DivFree: begin
                    ready_o  <= 1'b0;
                    result_o <= {`ZeroWord, `ZeroWord};
                    if (start_i == 1'b1 && annul_i == 1'b0) begin
                        if (opdata2_i == `ZeroWord) begin
                            state <= DivByZero;
                        end else begin
                            state          <= DivOn;
                            cnt            <= 6'd0;
                            dividend       <= 65'd0;
                            dividend[32:1] <= abs_op1;
                            divisor        <= abs_op2;
                        end
                    end
                end

                // MIPS leaves HI/LO architecturally UNPREDICTABLE on divide by
                // zero; ex.v mirrors the previous behaviour (HI=dividend,
                // LO=0xFFFFFFFF) so nothing here needs to be meaningful.
                DivByZero: begin
                    dividend <= 65'd0;
                    state    <= DivEnd;
                end

                DivOn: begin
                    if (annul_i == 1'b1) begin
                        state <= DivFree;
                    end else if (cnt != 6'd32) begin
                        if (div_temp[32] == 1'b1) begin
                            // divisor did not fit: shift in a 0
                            dividend <= {dividend[63:0], 1'b0};
                        end else begin
                            // it fit: store the difference and shift in a 1
                            dividend <= {div_temp[31:0], dividend[31:0], 1'b1};
                        end
                        cnt <= cnt + 6'd1;
                    end else begin
                        // reapply signs: quotient is negative when the operand
                        // signs differ, the remainder follows the dividend
                        if (signed_div_i && ((opdata1_i[31] ^ opdata2_i[31]) == 1'b1)) begin
                            dividend[31:0] <= (~dividend[31:0] + 32'd1);
                        end
                        if (signed_div_i && ((opdata1_i[31] ^ dividend[64]) == 1'b1)) begin
                            dividend[64:33] <= (~dividend[64:33] + 32'd1);
                        end
                        state <= DivEnd;
                        cnt   <= 6'd0;
                    end
                end

                DivEnd: begin
                    result_o <= {dividend[64:33], dividend[31:0]};
                    ready_o  <= 1'b1;
                    if (start_i == 1'b0) begin   // EX has taken the result
                        state    <= DivFree;
                        ready_o  <= 1'b0;
                        result_o <= {`ZeroWord, `ZeroWord};
                    end
                end

                default: state <= DivFree;

            endcase
        end
    end

endmodule
