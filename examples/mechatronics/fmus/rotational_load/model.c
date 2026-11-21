/*
 * Rotational load as an FMI co-simulation FMU (Embeddyn example).
 *   J dw/dt = tau - b w - coulomb tanh(w / 1e-3) - tau_load,   dtheta/dt = w
 * Integrated with fixed-step RK4 (h <= 10 us) inside each doStep.
 * Built twice by build_fmu.py: as FMI 2.0 (default) and with -DFMI3 as FMI 3.0.
 * Only the functions a co-simulation master needs for real variables are
 * implemented; others are omitted to keep the example short.
 */
#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define TOKEN "{8c4e810f-3df3-4a00-8276-176fa3c9f000}"
enum { VR_TAU, VR_J, VR_B, VR_TAU_LOAD, VR_COULOMB, VR_W, VR_THETA, VR_ACCEL, VR_COUNT };
enum { OK = 0, ERROR = 3 };

typedef struct {
    double v[VR_COUNT];
    double time;
} Model;

static double accel(const Model *m, double w)
{
    return (m->v[VR_TAU] - m->v[VR_B] * w - m->v[VR_COULOMB] * tanh(w / 1e-3) - m->v[VR_TAU_LOAD]) / m->v[VR_J];
}

static void *create(const char *token)
{
    if (!token || strcmp(token, TOKEN) != 0) {
        return NULL;
    }
    Model *m = calloc(1, sizeof(Model));
    if (m) {
        m->v[VR_J] = 0.02;
        m->v[VR_B] = 0.01;
    }
    return m;
}

static int set(void *c, const unsigned *vr, size_t n, const double *v)
{
    Model *m = c;
    for (size_t i = 0; i < n; i++) {
        if (vr[i] >= VR_COUNT || (vr[i] == VR_J && v[i] <= 0)) {
            return ERROR;
        }
        m->v[vr[i]] = v[i];
    }
    return OK;
}

static int get(void *c, const unsigned *vr, size_t n, double *v)
{
    Model *m = c;
    m->v[VR_ACCEL] = accel(m, m->v[VR_W]);
    for (size_t i = 0; i < n; i++) {
        if (vr[i] >= VR_COUNT) {
            return ERROR;
        }
        v[i] = m->v[vr[i]];
    }
    return OK;
}

static int step(void *c, double t, double h)
{
    Model *m = c;
    int n = (int)ceil(h / 1e-5 - 1e-9);
    if (n < 1) {
        n = 1;
    }
    double dt = h / n, w = m->v[VR_W], th = m->v[VR_THETA];
    for (int i = 0; i < n; i++) {
        double k1 = accel(m, w), k2 = accel(m, w + dt / 2 * k1), k3 = accel(m, w + dt / 2 * k2), k4 = accel(m, w + dt * k3);
        th += dt / 6 * (w + 2 * (w + dt / 2 * k1) + 2 * (w + dt / 2 * k2) + (w + dt * k3));
        w += dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4);
    }
    m->v[VR_W] = w;
    m->v[VR_THETA] = th;
    m->time = t + h;
    return isfinite(w) ? OK : ERROR;
}

#ifndef FMI3
/* ---- FMI 2.0 ---- */
const char *fmi2GetTypesPlatform(void) { return "default"; }
const char *fmi2GetVersion(void) { return "2.0"; }
void *fmi2Instantiate(const char *name, int type, const char *guid, const char *resources, const void *functions,
                      int visible, int logging)
{
    (void)name; (void)resources; (void)functions; (void)visible; (void)logging;
    return type == 1 ? create(guid) : NULL; /* 1 = fmi2CoSimulation */
}
int fmi2SetupExperiment(void *c, int tolDefined, double tol, double start, int stopDefined, double stop)
{
    (void)tolDefined; (void)tol; (void)stopDefined; (void)stop;
    ((Model *)c)->time = start;
    return OK;
}
int fmi2EnterInitializationMode(void *c) { (void)c; return OK; }
int fmi2ExitInitializationMode(void *c) { (void)c; return OK; }
int fmi2SetReal(void *c, const unsigned *vr, size_t n, const double *v) { return set(c, vr, n, v); }
int fmi2GetReal(void *c, const unsigned *vr, size_t n, double *v) { return get(c, vr, n, v); }
int fmi2DoStep(void *c, double t, double h, int noSetPrior) { (void)noSetPrior; return step(c, t, h); }
int fmi2Terminate(void *c) { (void)c; return OK; }
void fmi2FreeInstance(void *c) { free(c); }
#else
/* ---- FMI 3.0 ---- */
const char *fmi3GetVersion(void) { return "3.0"; }
void *fmi3InstantiateCoSimulation(const char *name, const char *token, const char *resources, bool visible,
                                  bool logging, bool eventMode, bool earlyReturn, const unsigned *required,
                                  size_t nRequired, void *env, void *logger, void *intermediate)
{
    (void)name; (void)resources; (void)visible; (void)logging; (void)eventMode; (void)earlyReturn;
    (void)required; (void)nRequired; (void)env; (void)logger; (void)intermediate;
    return create(token);
}
int fmi3EnterInitializationMode(void *c, bool tolDefined, double tol, double start, bool stopDefined, double stop)
{
    (void)tolDefined; (void)tol; (void)stopDefined; (void)stop;
    ((Model *)c)->time = start;
    return OK;
}
int fmi3ExitInitializationMode(void *c) { (void)c; return OK; }
int fmi3SetFloat64(void *c, const unsigned *vr, size_t n, const double *v, size_t nv) { (void)nv; return set(c, vr, n, v); }
int fmi3GetFloat64(void *c, const unsigned *vr, size_t n, double *v, size_t nv) { (void)nv; return get(c, vr, n, v); }
int fmi3DoStep(void *c, double t, double h, bool noSetPrior, bool *eventNeeded, bool *terminate, bool *early,
               double *lastTime)
{
    (void)noSetPrior;
    *eventNeeded = false;
    *terminate = false;
    *early = false;
    int status = step(c, t, h);
    *lastTime = ((Model *)c)->time;
    return status;
}
int fmi3Terminate(void *c) { (void)c; return OK; }
void fmi3FreeInstance(void *c) { free(c); }
#endif
