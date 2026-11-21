/*
 * Bare-metal STM32F4 DC-motor speed controller for the Embeddyn/Renode
 * co-simulation example (examples/mechatronics/dc-motor-renode.yaml).
 *
 *   ADC1 channel 0  <- speed sensor, counts = rad/s * 100 (12-bit)
 *   TIM1 CH1 (PA8)  -> PWM, 1 kHz, PWM mode 1, duty = controller output
 *
 * The PI loop runs once per PWM period, so the controller period (1 ms) is
 * exact in virtual time. Two pacing modes:
 *   -DUSE_IRQ    TIM1 update interrupt + WFI (Makefile default; the core
 *                sleeps between periods, so it needs about 10x less CPU to emulate)
 *   otherwise    poll the TIM1 update flag (`make POLL=1`)
 * The ADC
 * conversion is started at the end of each ISR and read at the start of the
 * next one, so nothing busy-waits; the speed sample is one period old, as in
 * many real drives. Gains and set-point
 * live in `motor_cal` (fixed address in .cal) so tests or tuning jobs can
 * change them over the Renode system bus without rebuilding.
 */
#include <stdint.h>

#define REG(addr) (*(volatile uint32_t *)(addr))

#define RCC_AHB1ENR REG(0x40023830u)
#define RCC_APB2ENR REG(0x40023844u)

#define TIM1_BASE   0x40010000u
#define TIM1_CR1    REG(TIM1_BASE + 0x00u)
#define TIM1_DIER   REG(TIM1_BASE + 0x0Cu)
#define TIM1_SR     REG(TIM1_BASE + 0x10u)
#define TIM1_EGR    REG(TIM1_BASE + 0x14u)
#define TIM1_CCMR1  REG(TIM1_BASE + 0x18u)
#define TIM1_CCER   REG(TIM1_BASE + 0x20u)
#define TIM1_PSC    REG(TIM1_BASE + 0x28u)
#define TIM1_ARR    REG(TIM1_BASE + 0x2Cu)
#define TIM1_CCR1   REG(TIM1_BASE + 0x34u)
#define TIM1_BDTR   REG(TIM1_BASE + 0x44u)

#define ADC1_BASE   0x40012000u
#define ADC1_SR     REG(ADC1_BASE + 0x00u)
#define ADC1_CR2    REG(ADC1_BASE + 0x08u)
#define ADC1_SQR1   REG(ADC1_BASE + 0x2Cu)
#define ADC1_SQR3   REG(ADC1_BASE + 0x34u)
#define ADC1_DR     REG(ADC1_BASE + 0x4Cu)

#define NVIC_ISER0  REG(0xE000E100u)
#define SCB_VTOR    REG(0xE000ED08u)
#define TIM1_UP_IRQ 25u

#define PWM_TOP     1000u          /* ARR + 1: 1 MHz / 1000 = 1 kHz */
#define DT          0.001f         /* controller period = PWM period */

struct motor_cal {
    uint32_t magic;                /* 0x4D4F5452 "MOTR" */
    float target_counts;           /* set-point in ADC counts (rad/s * 100) */
    float kp;                      /* duty per count */
    float ki;                      /* duty per count*second */
};

__attribute__((section(".cal"), used))
volatile struct motor_cal motor_cal = {0x4D4F5452u, 800.0f, 0.0012f, 0.008f};

/* Observable state for debugging/telemetry over the system bus. */
volatile uint32_t loop_count;
volatile uint32_t last_adc;
volatile float last_duty;

static float integral;

static void adc_start_ch0(void)
{
    ADC1_SR = 0;
    ADC1_CR2 |= (1u << 30);        /* SWSTART; result is read next period */
}

static void control_step(void)
{
    TIM1_SR = 0;                   /* clear UIF */

    uint32_t adc = ADC1_DR & 0xFFFu;
    float error = motor_cal.target_counts - (float)adc;
    float candidate = integral + error * DT;
    float duty = motor_cal.kp * error + motor_cal.ki * candidate;
    if (duty > 1.0f) {
        duty = 1.0f;
    } else if (duty < 0.0f) {
        duty = 0.0f;
    } else {
        integral = candidate;      /* conditional integration (anti-windup) */
    }

    /* Renode's STM32_Timer disables the channel for CCR = 0, so keep >= 1. */
    uint32_t ccr = (uint32_t)(duty * (float)PWM_TOP + 0.5f);
    TIM1_CCR1 = ccr < 1u ? 1u : ccr;

    last_adc = adc;
    last_duty = duty;
    loop_count++;
    adc_start_ch0();
}

void TIM1_UP_TIM10_IRQHandler(void)
{
    control_step();
}

extern const void *const vectors[];

int main(void)
{
    SCB_VTOR = (uint32_t)vectors;  /* don't rely on flash being aliased at 0 */
    RCC_AHB1ENR |= 1u;             /* GPIOA */
    RCC_APB2ENR |= (1u << 0) | (1u << 8);  /* TIM1, ADC1 */

    ADC1_SQR1 = 0;                 /* one conversion */
    ADC1_SQR3 = 0;                 /* channel 0 */
    ADC1_CR2 = 1u;                 /* ADON */
    adc_start_ch0();

    TIM1_PSC = 9u;                 /* 10 MHz timer clock -> 1 MHz */
    TIM1_ARR = PWM_TOP - 1u;
    TIM1_CCR1 = 1u;
    TIM1_CCMR1 = (6u << 4);        /* OC1M = PWM mode 1 */
    TIM1_CCER = 1u;                /* CC1E */
    TIM1_BDTR = (1u << 15);        /* MOE (advanced timer) */
    TIM1_DIER = 1u;                /* UIE */
    TIM1_EGR = 1u;                 /* UG */
    TIM1_SR = 0;
#ifdef USE_IRQ
    NVIC_ISER0 = (1u << TIM1_UP_IRQ);
    TIM1_CR1 = 1u;                 /* CEN */
    /* The UG event above leaves IRQ 25 pending, so enabling it interrupts
     * right away. Without the barrier, Renode takes that interrupt and also
     * executes the following WFI from the same translation block: the core
     * then sleeps at the handler entry with IRQ 25 active, and no later
     * timer interrupt can wake it. ISB ends the block first (ARM recommends
     * DSB+ISB after NVIC enables before WFI anyway). */
    __asm volatile ("dsb\n\tisb" ::: "memory");
    for (;;) {
        __asm volatile ("wfi");
    }
#else
    TIM1_CR1 = 1u;                 /* CEN */
    for (;;) {
        while ((TIM1_SR & 1u) == 0) {
        }                          /* wait for the next PWM period */
        control_step();
    }
#endif
}
