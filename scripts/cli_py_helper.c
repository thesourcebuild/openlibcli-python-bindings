#if defined(_WIN32) || defined(__CYGWIN__)
#define CLI_PY_API __declspec(dllexport)
#else
#define CLI_PY_API __attribute__((visibility("default")))
#endif

#include "cli.h"
#include <stdlib.h>
#include <string.h>

/* ── cli_t / cli_cmd_t allocation ─────────────────────────────────────────── */

CLI_PY_API size_t cli_py_sizeof(void) {
    return sizeof(cli_struct_t);
}

CLI_PY_API size_t cli_py_cmd_sizeof(void) {
    return sizeof(cli_cmd_struct_t);
}

CLI_PY_API void *cli_py_alloc(void) {
    return calloc(1, sizeof(cli_struct_t));
}

CLI_PY_API void *cli_py_cmd_pool_alloc(size_t count) {
    return calloc(count, sizeof(cli_cmd_struct_t));
}

CLI_PY_API void cli_py_free(void *p) {
    free(p);
}

/* ── Non-variadic wrappers for output functions ───────────────────────────── */

CLI_PY_API int cli_py_print(cli_struct_t *cli, const char *msg) {
    return cli_print(cli, "%s", msg);
}

CLI_PY_API int cli_py_println(cli_struct_t *cli, const char *msg) {
    return cli_println(cli, "%s", msg);
}

CLI_PY_API int cli_py_error(cli_struct_t *cli, const char *msg) {
    return cli_error(cli, "%s", msg);
}
