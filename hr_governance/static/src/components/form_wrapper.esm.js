import {markup, onMounted, useState} from "@odoo/owl";
import {DeleteRolesConfirmationDialog} from "./delete_roles_confirmation_dialog.esm";
import {FormController} from "@web/views/form/form_controller";
import {_t} from "@web/core/l10n/translation";
import {executeButtonCallback} from "@web/views/view_button/view_button_hook";
import {formView} from "@web/views/form/form_view";
import {isEmpty} from "../utils/helpers.esm";
import {registry} from "@web/core/registry";

export class FormWrapperController extends FormController {
    setup() {
        super.setup();
    }

    async deleteRecord() {
        const data = await this.model.orm.call(
            "governance.circle",
            "js_get_deleted_circle_info",
            [this.model.root.evalContext.active_id]
        );
        this.dialogService.add(DeleteRolesConfirmationDialog, {
            body: markup(
                _t(
                    `Deleting this Circle will also delete its associated roles (<b>Impact ${data.subcircles} sub-circles, ${data.roles} roles, ${data.employees} employees)</b>.
If you wish to preserve the roles, make sure to unlink them from their circle beforehand.

Are you sure you want to proceed?`
                )
            ),
            confirm: async () => {
                const typing = prompt("Please type DELETE");
                if (typing === "DELETE") {
                    await this.model.root.delete();
                    this.ui.bus.trigger("governance:form_deleted_record", {
                        deletedResId: this.props.resId,
                    });
                }
            },
        });
    }

    async create(ev) {
        const additionalContext = {};

        // Prefil circle/role
        const buttonType = ev.target.dataset.type;
        const method = buttonType === "circle" ? `_create_circle` : `_create_role`;
        await this[method](additionalContext);

        // Prefil parent_id
        additionalContext.default_parent_id = this.props.resId || false;
        if (isEmpty(additionalContext) === false) {
            await executeButtonCallback(this.ui.activeElement, () =>
                this.model.load({
                    resId: false,
                    context: {
                        ...this.props.context,
                        ...additionalContext,
                    },
                })
            );
            // TODO: is this needed?
        } else return super.create(ev);
    }

    _create_circle(context = {}) {
        context.default_is_circle = true;
    }

    _create_role(context = {}) {
        context.default_is_circle = false;
    }
}

FormWrapperController.template = `hr_governance.FormWrapperView`;

export const formwrapperView = {
    ...formView,
    Controller: FormWrapperController,
};

registry.category("views").add("formwrapper", formwrapperView);
